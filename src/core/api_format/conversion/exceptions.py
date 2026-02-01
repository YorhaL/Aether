"""
格式转换异常

用于严格模式转换失败时抛出，让编排器可以尝试下一个候选。
"""


class FormatConversionError(Exception):
    """
    格式转换失败异常

    在严格模式下，转换失败会抛出此异常，
    让 Orchestrator 可以捕获并尝试下一个候选。
    """

    def __init__(self, source_format: str, target_format: str, message: str) -> None:
        self.source_format = source_format
        self.target_format = target_format
        self.message = message
        super().__init__(f"格式转换失败 ({source_format} -> {target_format}): {message}")


__all__ = [
    "FormatConversionError",
]
