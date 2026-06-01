"""
公共错误基础设施

- ErrorCode：枚举基类，各域继承此类定义错误码枚举
- BusinessError：统一业务异常
- UnifiedResponse：统一 HTTP 200 响应
"""

from enum import Enum

from fastapi.responses import JSONResponse


class ErrorCode(Enum):
    """错误码枚举基类

    各域继承此类定义枚举成员：
        class ResourceErrorCode(ErrorCode):
            DOCUMENT_NOT_FOUND = ("404001", "文档不存在")
            VERSION_NOT_FOUND  = ("404002", "版本不存在")
    """

    def __new__(cls, code: str, description: str):
        obj = object.__new__(cls)
        obj._code = code
        obj._description = description
        return obj

    @property
    def value(self) -> str:
        return self._code

    @property
    def description(self) -> str:
        return self._description


class BusinessError(Exception):
    """统一业务异常"""

    def __init__(self, code: ErrorCode, description: str | None = None):
        self.code = code.value
        self.description = description if description is not None else code.description


class UnifiedResponse:
    """统一 HTTP 200 响应"""

    _OK = "000000"

    def __init__(self):
        self._code = self._OK
        self._description = "成功"
        self._content = None

    def ok(self, content=None) -> None:
        self._code = self._OK
        self._description = "成功"
        self._content = content

    def error(self, e: BusinessError) -> None:
        self._code = e.code
        self._description = e.description
        self._content = None

    def to_json(self) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={
                "code": self._code,
                "description": self._description,
                "content": self._content,
            },
        )
