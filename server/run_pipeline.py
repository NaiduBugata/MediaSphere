from orchestrator import PipelineOrchestrator


def main() -> int:
    orchestrator = PipelineOrchestrator()
    orchestrator.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
