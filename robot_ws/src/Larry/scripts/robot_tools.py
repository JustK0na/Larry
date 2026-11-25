#!/usr/bin/env python3
import json
from typing import Any, Dict, Tuple
from pydantic import BaseModel, Field, ValidationError

# Wspólne limity bezpieczeństwa (spójne ze sterownikiem robot_driver.py)
MAX_LINEAR_SPEED = 5
MAX_ANGULAR_SPEED = 5.0
MIN_DURATION = 0.5
MAX_DURATION = 3.0


class MoveRobotArgs(BaseModel):
    linear_x: float = Field(
        ...,
        ge=-MAX_LINEAR_SPEED,
        le=MAX_LINEAR_SPEED,
        description=(
            f"Forward/backward velocity in m/s (range -{MAX_LINEAR_SPEED} to {MAX_LINEAR_SPEED}). "
            "Positive moves forward, negative reverses, 0.0 rotates in place."
        ),
    )
    angular_z: float = Field(
        ...,
        ge=-MAX_ANGULAR_SPEED,
        le=MAX_ANGULAR_SPEED,
        description=(
            f"Angular velocity in rad/s (range -{MAX_ANGULAR_SPEED} to {MAX_ANGULAR_SPEED}). "
            "Positive turns left, negative turns right, 0.0 drives straight."
        ),
    )
    duration: float = Field(
        ...,
        ge=MIN_DURATION,
        le=MAX_DURATION,
        description=f"Movement duration in seconds (range {MIN_DURATION} to {MAX_DURATION}).",
    )
    reason: str = Field(
        ...,
        min_length=3,
        description="Short explanation of what you see in the image and why you chose these parameters.",
    )


class StopRobotArgs(BaseModel):
    reason: str = Field(
        ...,
        min_length=3,
        description="target goal reached right in front of the robot.",
    )


# Definicja narzędzi przekazywana bezpośrednio do ollama.Client.chat(..., tools=ROBOT_TOOLS)
ROBOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "move_robot",
            "description": (
                "Move the mobile robot with custom linear and angular velocities for a chosen duration. "
                "Combine linear_x and angular_z to drive smoothly in a curve around obstacles. "
                "angular_z below 0 means turning right and positive value means turning left. "
                "linear_x below 0 means backing up and positive value means going forward. "
                "use values below 0.5 ONLY for for small precise adjustements, normally use larger values. "
            ),
            "parameters": MoveRobotArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_robot",
            "description": (
                "FINAL ACTION: Terminate the mission. Call this ONLY when you clearly see the target goal "
                "right in front of the robot and have reached it. "
                "NEVER call stop_robot just because the target is not visible yet. keep searching by rotating and driving."
            ),
            "parameters": StopRobotArgs.model_json_schema(),
        },
    },
]


def validate_tool_call(func_name: str, raw_args: Any) -> Tuple[Dict[str, Any], str, str]:
    """
    Waliduje wywołanie narzędzia z LLM-a przez Pydantic.
    Zwraca krotkę: (cmd_payload_dla_ROS, feedback_dla_LLM, komunikat_do_logu).
    """
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            return (
                {"action": "stop"},
                f"Error: invalid JSON arguments ({e}). Robot stopped for safety.",
                f"[BŁĄD JSON] {e}",
            )

    if not isinstance(raw_args, dict):
        return (
            {"action": "stop"},
            "Error: tool arguments must be a JSON object. Robot stopped.",
            f"[BŁĄD TYPU] Otrzymano {type(raw_args).__name__}",
        )

    try:
        if func_name == "move_robot":
            args = MoveRobotArgs(**raw_args)
            payload = {
                "action": "move",
                "linear_x": round(args.linear_x, 3),
                "angular_z": round(args.angular_z, 3),
                "duration": round(args.duration, 2),
            }
            feedback = (
                f"Executed move_robot: linear_x={payload['linear_x']} m/s, "
                f"angular_z={payload['angular_z']} rad/s, duration={payload['duration']}s."
            )
            log_msg = f"[QWEN MOVE] {args.reason} | {payload}"
            return payload, feedback, log_msg

        if func_name == "stop_robot":
            args = StopRobotArgs(**raw_args)
            payload = {"action": "stop"}
            feedback = "Executed stop_robot: robot is stopped."
            log_msg = f"[QWEN STOP] {args.reason}"
            return payload, feedback, log_msg

        return (
            {"action": "stop"},
            f"Error: unknown tool '{func_name}'. Available tools: move_robot, stop_robot.",
            f"[NIEZNANE NARZĘDZIE] {func_name}",
        )

    except ValidationError as ve:
        short_err = "; ".join(
            f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
            for err in ve.errors()
        )
        return (
            {"action": "stop"},
            f"Validation error ({short_err}). Adjust values to allowed ranges. Robot stopped.",
            f"[WALIDACJA ODRZUCONA] {short_err} | surowe argumenty: {raw_args}",
        )


def build_lfm_command(raw_output: str) -> Tuple[Dict[str, Any], str]:
    """
    Mapuje klasyczną odpowiedź jednosłowną z LFM (DRIVE/LEFT/RIGHT/STOP)
    na ten sam format JSON, którego używa robot_driver.py.
    """
    lfm_map = {
        "DRIVE": {"action": "move", "linear_x": 0.3, "angular_z": 0.0, "duration": 1.5},
        "LEFT":  {"action": "move", "linear_x": 0.0, "angular_z": 0.5, "duration": 1.5},
        "RIGHT": {"action": "move", "linear_x": 0.0, "angular_z": -0.5, "duration": 1.5},
        "STOP":  {"action": "stop"},
    }

    words = raw_output.strip().upper().split()
    decision = "STOP"
    if words:
        for move in ("DRIVE", "STOP", "LEFT", "RIGHT"):
            if move in words[0]:
                decision = move
                break

    return lfm_map[decision], decision
