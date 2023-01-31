from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SLARequest(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class SLASetResponse(_message.Message):
    __slots__ = ["metric", "seasonality"]
    class MetricEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    class Seasonality(_message.Message):
        __slots__ = ["add", "mul"]
        ADD_FIELD_NUMBER: _ClassVar[int]
        MUL_FIELD_NUMBER: _ClassVar[int]
        add: int
        mul: int
        def __init__(self, add: _Optional[int] = ..., mul: _Optional[int] = ...) -> None: ...
    METRIC_FIELD_NUMBER: _ClassVar[int]
    SEASONALITY_FIELD_NUMBER: _ClassVar[int]
    metric: _containers.ScalarMap[str, str]
    seasonality: SLASetResponse.Seasonality
    def __init__(self, metric: _Optional[_Mapping[str, str]] = ..., seasonality: _Optional[_Union[SLASetResponse.Seasonality, _Mapping]] = ...) -> None: ...
