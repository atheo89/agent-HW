import json
import os
import time
from datetime import datetime


class AgentTracer:
    def __init__(self, enabled=False, trace_dir="traces"):
        self.enabled = enabled
        self.trace_dir = trace_dir
        self.trace = []
        self.start_time = time.time()

        if self.enabled:
            os.makedirs(trace_dir, exist_ok=True)

    # =====================================================
    # GENERIC EVENT LOGGER
    # =====================================================

    def log(self, event_type, **data):
        if not self.enabled:
            return

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            "data": data,
        }

        self.trace.append(event)


    # =====================================================
    # GENERIC SEMANTIC EVENTS
    # =====================================================

    def tool_call(self, tool_name, input_data=None):
        self.log(
            "tool_call",
            tool=tool_name,
            input=input_data,
        )


    def tool_result(self, tool_name, output_data=None):
        self.log(
            "tool_result",
            tool=tool_name,
            output=output_data,
        )


    def reasoning_step(self, thought):
        self.log(
            "reasoning_step",
            thought=thought,
        )


    def planning_step(self, plan):
        self.log(
            "planning_step",
            plan=plan,
        )


    def memory_access(self, operation, details=None):
        self.log(
            "memory_access",
            operation=operation,
            details=details,
        )


    def token_usage(
        self,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
    ):
        self.log(
            "token_usage",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


    def model_decision(self, decision, confidence=None):
        self.log(
            "model_decision",
            decision=decision,
            confidence=confidence,
        )


    def retry_event(self, reason, next_attempt):
        self.log(
            "retry_event",
            reason=reason,
            next_attempt=next_attempt,
        )


    def evaluation_metric(self, metric_name, value):
        self.log(
            "evaluation_metric",
            metric=metric_name,
            value=value,
        )


    def error_event(self, error_type, message):
        self.log(
            "error_event",
            error_type=error_type,
            message=message,
        )


    # =====================================================
    # STEP TIMER
    # =====================================================

    def time_block(self, block_name):
        return TraceTimer(self, block_name)

    # =====================================================
    # SAVE TRACE
    # =====================================================

    def save(self):
        if not self.enabled:
            return

        duration = time.time() - self.start_time

        self.log(
            "trace_summary",
            total_events=len(self.trace),
            total_duration_seconds=duration,
        )

        filename = datetime.utcnow().strftime("trace_%Y%m%d_%H%M%S.json")
        filepath = os.path.join(self.trace_dir, filename)

        with open(filepath, "w") as f:
            json.dump(self.trace, f, indent=2)

        print(f"\nTrace saved to: {filepath}")


# =========================================================
# CONTEXT MANAGER FOR TIMING
# =========================================================

class TraceTimer:
    def __init__(self, tracer, block_name):
        self.tracer = tracer
        self.block_name = block_name

    def __enter__(self):
        self.start = time.time()

        self.tracer.log(
            "block_started",
            block=self.block_name,
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start

        self.tracer.log(
            "block_finished",
            block=self.block_name,
            duration_seconds=duration,
        )
