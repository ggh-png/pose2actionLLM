"""Server pipeline: inspect data, evaluate models, and write actionable feedback."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pose_llm_classifier.data import KEYPOINTS, LABELS, iter_samples, write_json  # noqa: E402
from pose_llm_classifier.evaluation import evaluate  # noqa: E402
from pose_llm_classifier.features import extract_features  # noqa: E402
from pose_llm_classifier.inference import Classifier, build_messages  # noqa: E402
from pose_llm_classifier.preprocessing import preprocess  # noqa: E402
from pose_llm_classifier.visualization import plot_comparison  # noqa: E402


class PipelineError(Exception):
    pass


def fingerprint(sample):
    points = preprocess(sample)["keypoints"]
    coordinates = {
        name: [round(point["x"], 6), round(point["y"], 6)] if point else None
        for name in sorted(KEYPOINTS)
        for point in [points.get(name)]
    }
    return hashlib.sha256(json.dumps(coordinates, sort_keys=True).encode()).hexdigest()


def doctor():
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "disk_free_gib": round(shutil.disk_usage(".").free / 2**30, 2),
    }
    if Path("/proc/meminfo").exists():
        info["memory"] = {
            line.split(":")[0]: line.split(":")[1].strip()
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith(("MemTotal:", "MemAvailable:"))
        }
    if shutil.which("nvidia-smi"):
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        info["gpu"] = result.stdout.strip() if result.returncode == 0 else "nvidia-smi failed"
    else:
        info["gpu"] = "nvidia-smi unavailable; mock/inspection/external endpoint still usable"
    return info


def inspect_dataset(path, output, threshold, per_class):
    """Stream full validation, keep only fingerprints/counts and a bounded preview."""
    counts, missing, selected, seen = Counter(), Counter(), Counter(), set()
    total = synthetic = duplicates = mismatches = unlabeled = 0
    with (
        (output / "preprocessed.jsonl").open("w", encoding="utf-8") as processed_stream,
        (output / "prompts.jsonl").open("w", encoding="utf-8") as prompt_stream,
    ):
        for index, sample in enumerate(iter_samples(path)):
            total += 1
            label = sample.get("label")
            unlabeled += label is None
            counts[str(label)] += 1
            synthetic += sample.get("synthetic") is True
            processed = preprocess(sample, threshold)
            for name in KEYPOINTS:
                if not processed["keypoints"].get(name):
                    missing[name] += 1
            features = extract_features(processed)
            up = [features[f"{side}_elbow_above_shoulder"] for side in ("left", "right")]
            # A visible raised elbow proves UP; DOWN needs both elbows visible.
            observable = any(value is True for value in up) or all(
                value is not None for value in up
            )
            if label is not None and observable and any(up) != bool(label % 2):
                mismatches += 1
            digest = fingerprint(sample)
            duplicates += digest in seen
            seen.add(digest)
            processed_stream.write(json.dumps(dict(processed, features=features)) + "\n")
            prompt_stream.write(
                json.dumps(
                    {"index": index, "messages": build_messages(sample, min_confidence=threshold)}
                )
                + "\n"
            )
            if selected[str(label)] < per_class:
                plot_comparison(
                    sample, output / "visualization" / f"sample_{index:05d}", True, threshold
                )
                selected[str(label)] += 1
    if not total:
        raise PipelineError("Input dataset is empty.")
    return {
        "total": total,
        "class_counts": dict(counts),
        "unlabeled": unlabeled,
        "synthetic": synthetic,
        "duplicates": duplicates,
        "missing_after_filter": dict(missing),
        "elbow_label_mismatches": mismatches,
    }, seen


def read_examples(path, test_fingerprints):
    if not path:
        return []
    examples = list(iter_samples(path))
    if not examples or any(s.get("label") is None for s in examples):
        raise PipelineError("Few-shot examples must be nonempty and fully labeled.")
    if any(fingerprint(s) in test_fingerprints for s in examples):
        raise PipelineError(
            "Few-shot/test overlap detected after coordinate normalization. Split the data first."
        )
    return examples


def endpoint_models(base_url, timeout=5):
    request = urllib.request.Request(base_url.rstrip("/") + "/models")
    if os.getenv("POSE_API_KEY"):
        request.add_header("Authorization", "Bearer " + os.environ["POSE_API_KEY"])
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return [row["id"] for row in json.load(response)["data"]]


def wait_for_endpoint(args, model, process=None):
    deadline = time.monotonic() + args.startup_timeout
    while True:
        if process and process.poll() is not None:
            raise PipelineError(
                "Model server exited. Read the model log; check GPU memory, driver and model access."
            )
        try:
            models = endpoint_models(args.base_url)
            if model not in models:
                raise PipelineError(f"Model {model!r} is not served; endpoint models: {models}")
            return
        except (urllib.error.URLError, TimeoutError, OSError):
            if not process or time.monotonic() >= deadline:
                raise PipelineError(
                    "Model endpoint unavailable. Check --base-url, POSE_API_KEY or --start-model-server."
                ) from None
            time.sleep(2)


def stop_server(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


@contextmanager
def model_endpoint(args, model, log_path):
    if not args.start_model_server:
        wait_for_endpoint(args, model)
        yield
        return
    parts = urlsplit(args.base_url)
    if parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.path.rstrip("/") != "/v1":
        raise PipelineError("--start-model-server requires http://127.0.0.1:PORT/v1")
    port = parts.port or 80
    if not shutil.which("nvidia-smi"):
        raise PipelineError("Auto-start supports NVIDIA Linux servers; nvidia-smi is unavailable.")
    executable = Path(sys.executable).parent / "vllm"
    if not executable.exists():
        raise PipelineError(
            "vLLM is not installed. Run the wrapper with --install-vllm on the GPU server."
        )
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise PipelineError(
                f"Port {port} is occupied. Use the existing endpoint without --start-model-server."
            )
    command = [
        str(executable),
        "serve",
        model,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--max-model-len",
        str(args.max_model_len),
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--default-chat-template-kwargs",
        '{"enable_thinking": false}',
    ]
    env = os.environ.copy()
    # Keep authentication for the local server and client consistent without putting the key in argv.
    if os.getenv("POSE_API_KEY"):
        env["VLLM_API_KEY"] = os.environ["POSE_API_KEY"]
    else:
        env.pop("VLLM_API_KEY", None)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env
        )
        try:
            wait_for_endpoint(args, model, process)
            yield
        finally:
            stop_server(process)


def feedback(state, output):
    lines = [
        "# Pose 자동 실행 피드백",
        "",
        f"상태: **{state['status']}**",
        "",
        f"실행 모드: `{state['mode']}`",
        "",
        "손목/발목 없이 어깨·팔꿈치·골반·무릎 8개 관절을 사용합니다. HAND_UP은 팔꿈치 높이의 대리 기준입니다.",
        "",
    ]
    if state.get("error"):
        lines += ["## 중단 원인", "", state["error"], ""]
    data = state.get("dataset")
    if data:
        lines += [
            "## 데이터 점검",
            "",
            f"전체 {data['total']}개 / 합성 {data['synthetic']}개 / 정답 누락 {data['unlabeled']}개",
            "",
            "| ID | 클래스 | 수량 |",
            "|---|---|---|",
        ]
        lines += [
            f"| {i} | {name} | {data['class_counts'].get(str(i), 0)} |"
            for i, name in enumerate(LABELS)
        ]
        lines += [
            "",
            f"정규화 좌표 중복: {data['duplicates']}개. 팔꿈치 기준과 라벨 불일치: {data['elbow_label_mismatches']}개.",
            "",
        ]
        if data["synthetic"]:
            lines += ["- 합성 데이터가 포함되어 있습니다. 실제 모델 성능의 근거로 사용하지 마세요."]
        if data["duplicates"]:
            lines += ["- 중복 좌표를 제거하고 사람·촬영 세션 단위로 train/test 분리를 확인하세요."]
        if data["elbow_label_mismatches"]:
            lines += [
                "- 라벨 불일치가 있습니다. 팔 올림 정의와 좌표축·라벨 매핑을 검토하세요. 자동으로 라벨을 변경하지 않았습니다."
            ]
        if any(data["missing_after_filter"].values()):
            lines += [
                "- 누락/필터 관절 수: "
                + json.dumps(data["missing_after_filter"], ensure_ascii=False)
            ]
        if any(not data["class_counts"].get(str(i)) for i in range(4)):
            lines += ["- 일부 클래스가 없습니다. 네 클래스의 실제 데이터를 확보하세요."]
        lines += [
            "",
            "## 확인할 파일",
            "",
            "- [정규화 좌표와 feature](preprocessed.jsonl)",
            "- [Zero-shot 프롬프트](prompts.jsonl)",
            "",
        ]
        for path in sorted((output / "visualization").glob("*/raw_pose.png")):
            raw = path.relative_to(output).as_posix()
            pre = path.with_name("preprocessed_pose.png").relative_to(output).as_posix()
            lines += [f"- {path.parent.name}: [원본]({raw}) / [전처리]({pre})"]
        lines += [""]
    results = state.get("evaluations", [])
    if results:
        lines += [
            "## 모델 평가",
            "",
            "| 모델 | 방식 | Accuracy | 실패 | 평균 지연 (s) |",
            "|---|---|---|---|---|",
        ]
        for row in results:
            m = row["metrics"]
            lines += [
                f"| {m['model']} | {row['strategy']} | {m['accuracy']:.3f} | {m['failed']} | {m['mean_latency_seconds']:.3f} |"
            ]
        lines += [
            "",
            "실패한 응답은 accuracy에서 오답으로 계산합니다. 클래스별 지표·혼동행렬은 실패 응답을 제외합니다.",
            "",
        ]
        for row in results:
            path, m = row["directory"], row["metrics"]
            lines += [
                f"- `{path}`: [지표]({path}/metrics.json), [응답과 프롬프트]({path}/predictions.jsonl)"
            ]
            confusion = m["confusion_matrix"]
            pairs = sorted(
                ((confusion[a][b], a, b) for a in range(4) for b in range(4) if a != b),
                reverse=True,
            )
            if pairs[0][0]:
                count, a, b = pairs[0]
                lines += [
                    f"  - 가장 빈번한 혼동: {LABELS[a]} → {LABELS[b]} ({count}개). 해당 errors PNG와 원본 좌표를 확인하세요."
                ]
            if m["failed"]:
                lines += [
                    "  - 실패 응답이 있습니다. raw response와 모델 로그에서 출력 형식, thinking 설정, timeout을 확인하세요."
                ]
        if state["mode"] == "mock":
            lines += [
                "",
                "Mock은 항상 0을 반환합니다. 성능 비교나 최적 모델 선정에 사용할 수 없습니다.",
            ]
        elif (
            data and not data["synthetic"] and all(row["metrics"]["failed"] == 0 for row in results)
        ):
            best = max(
                results,
                key=lambda row: (
                    row["metrics"]["accuracy"],
                    -row["metrics"]["mean_latency_seconds"],
                ),
            )
            lines += [
                "",
                f"이번 실행 내 참고 1위: `{best['metrics']['model']}` / {best['strategy']}. "
                "데이터 누수·실제 대표성 검토 전에는 최종 모델 선정으로 해석하지 마세요.",
            ]
    lines += ["", "## 다음 작업", ""]
    if state["status"] == "needs_review":
        lines += [
            "원본/전처리 PNG와 prompts.jsonl을 사람이 확인한 후 동일 입력으로 `--visualization-reviewed`를 추가해 다시 실행하세요."
        ]
    elif state["status"] == "failed":
        lines += [
            "중단 원인을 수정하고 재실행하세요. 새 실행 폴더가 생성되므로 기존 결과는 보존됩니다."
        ]
    else:
        lines += [
            "오분류 이미지와 실제 데이터를 검토하고, 별도 few-shot 예시로 재평가하세요. 실제 모델을 선정한 뒤 FastAPI 연결과 부하 테스트를 진행하세요."
        ]
    (output / "feedback.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(output / "run.json", state)
    print(f"\n[{state['status']}] {output / 'feedback.md'}", flush=True)
    if data:
        print(
            f"Samples={data['total']}, synthetic={data['synthetic']}, duplicates={data['duplicates']}, "
            f"label mismatches={data['elbow_label_mismatches']}",
            flush=True,
        )
    if state.get("error"):
        print(state["error"], flush=True)
    for row in results:
        m = row["metrics"]
        print(
            f"{m['model']} / {row['strategy']}: accuracy={m['accuracy']:.3f}, failures={m['failed']}",
            flush=True,
        )


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__,
        epilog="Wrapper: bash scripts/run_server.sh installs base dependencies. Add --install-vllm only on the GPU server to install vLLM.",
    )
    p.add_argument("--input", default="data/sample/synthetic_100.jsonl")
    p.add_argument("--mode", choices=("inspect", "mock", "remote"), default="inspect")
    p.add_argument("--output-root", type=Path, default=Path("results/runs"))
    p.add_argument("--models", nargs="+", default=["Qwen/Qwen3-4B"])
    p.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    p.add_argument(
        "--few-shot", help="Separate labeled training examples; checked for coordinate overlap"
    )
    p.add_argument("--visualization-reviewed", action="store_true")
    p.add_argument(
        "--start-model-server",
        action="store_true",
        help="Start/stop local vLLM per model; may download weights",
    )
    p.add_argument("--startup-timeout", type=int, default=1800)
    p.add_argument("--request-timeout", type=int, default=60)
    p.add_argument("--max-model-len", type=int, default=8192)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.85)
    p.add_argument("--min-confidence", type=float, default=0)
    p.add_argument("--preview-per-class", type=int, default=3)
    p.add_argument("--no-error-plots", action="store_true")
    args = p.parse_args(argv)
    if not 0 <= args.min_confidence <= 1 or not 0 < args.gpu_memory_utilization < 1:
        p.error("confidence must be in [0,1]; GPU memory utilization must be in (0,1)")
    if (
        min(args.preview_per_class, args.startup_timeout, args.request_timeout, args.max_model_len)
        < 1
    ):
        p.error("sample counts, timeouts and context length must be positive")
    if args.start_model_server and args.mode != "remote":
        p.error("--start-model-server requires --mode remote")
    return args


def run(args):
    args.output_root.mkdir(parents=True, exist_ok=True)
    # mkdtemp prevents collisions between simultaneous runs and repeated invocations.
    import tempfile

    output = Path(
        tempfile.mkdtemp(
            prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=args.output_root
        )
    )
    state = {
        "status": "running",
        "mode": args.mode,
        "input": str(Path(args.input).resolve()),
        "models": args.models,
        "visualization_reviewed": args.visualization_reviewed,
        "min_confidence": args.min_confidence,
        "evaluations": [],
    }
    code = 0
    try:
        print(f"Output: {output}", flush=True)
        state["environment"] = doctor()
        write_json(output / "environment.json", state["environment"])
        print("[1/4] Validating data, writing plots and prompts", flush=True)
        state["dataset"], fingerprints = inspect_dataset(
            args.input, output, args.min_confidence, args.preview_per_class
        )
        examples = read_examples(args.few_shot, fingerprints)
        if args.mode == "inspect" or (args.mode == "remote" and not args.visualization_reviewed):
            state["status"] = "needs_review"
            return 2 if args.mode == "remote" else 0
        if state["dataset"]["unlabeled"]:
            raise PipelineError(
                "Evaluation requires a ground-truth label for every sample. Use --mode inspect for unlabeled input."
            )
        for index, model in enumerate(args.models):
            print(f"[2/4] Preparing {model}", flush=True)
            if args.mode == "remote":
                context = model_endpoint(args, model, output / f"model_{index:02d}.log")
            else:
                from contextlib import nullcontext

                context = nullcontext()
            with context:
                classifier = Classifier(
                    "mock" if args.mode == "mock" else "remote",
                    model,
                    args.base_url,
                    args.visualization_reviewed,
                    args.request_timeout,
                )
                print("[3/4] Single-sample inference check", flush=True)
                first = next(iter_samples(args.input))
                write_json(
                    output / f"smoke_{index:02d}.json",
                    classifier.predict(first, min_confidence=args.min_confidence),
                )
                strategies = [("zero_shot", [])] + ([("few_shot", examples)] if examples else [])
                for strategy, shots in strategies:
                    folder = f"model_{index:02d}/{strategy}"
                    print(f"[4/4] Evaluating {model} / {strategy}", flush=True)
                    metrics = evaluate(
                        iter_samples(args.input),
                        classifier,
                        output / folder,
                        shots,
                        not args.no_error_plots,
                        args.min_confidence,
                    )
                    state["evaluations"].append(
                        {"directory": folder, "strategy": strategy, "metrics": metrics}
                    )
        state["status"] = (
            "completed_with_failures"
            if any(r["metrics"]["failed"] for r in state["evaluations"])
            else "completed"
        )
        code = 1 if state["status"] == "completed_with_failures" else 0
    except KeyboardInterrupt:
        state.update(status="failed", error="Interrupted by user; owned model server stopped.")
        code = 130
    except Exception as exc:
        state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        code = 1
    finally:
        feedback(state, output)
    return code


if __name__ == "__main__":
    sys.exit(run(parse_args()))
