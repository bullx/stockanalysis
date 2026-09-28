def adapt_prompts_for_model(system_prompt: str, user_message: str, mode: str) -> dict[str, str]:
    if mode == "inject":
        return {
            "system": "",
            "user": (
                "You must follow these instructions precisely for this entire response:\n\n"
                f"{system_prompt}\n\n---\n\nNow complete this task:\n{user_message}"
            ),
        }
    if mode == "chatml":
        return {
            "system": "",
            "user": (
                f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
                f"<|im_start|>user\n{user_message}<|im_end|>\n"
                "<|im_start|>assistant\n"
            ),
        }
    return {"system": system_prompt, "user": user_message}
