# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: sla.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\tsla.proto\x12\x03sla\"\x0c\n\nSLARequest\"\xe4\x01\n\x0eSLASetResponse\x12/\n\x06metric\x18\x01 \x03(\x0b\x32\x1f.sla.SLASetResponse.MetricEntry\x12\x39\n\x0bseasonality\x18\x02 \x01(\x0b\x32\x1f.sla.SLASetResponse.SeasonalityH\x00\x88\x01\x01\x1a-\n\x0bMetricEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\x1a\'\n\x0bSeasonality\x12\x0b\n\x03\x61\x64\x64\x18\x01 \x01(\r\x12\x0b\n\x03mul\x18\x02 \x01(\rB\x0e\n\x0c_seasonality2C\n\nSlaService\x12\x35\n\tGetSLASet\x12\x0f.sla.SLARequest\x1a\x13.sla.SLASetResponse\"\x00\x30\x01\x62\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'sla_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _SLASETRESPONSE_METRICENTRY._options = None
  _SLASETRESPONSE_METRICENTRY._serialized_options = b'8\001'
  _SLAREQUEST._serialized_start=18
  _SLAREQUEST._serialized_end=30
  _SLASETRESPONSE._serialized_start=33
  _SLASETRESPONSE._serialized_end=261
  _SLASETRESPONSE_METRICENTRY._serialized_start=159
  _SLASETRESPONSE_METRICENTRY._serialized_end=204
  _SLASETRESPONSE_SEASONALITY._serialized_start=206
  _SLASETRESPONSE_SEASONALITY._serialized_end=245
  _SLASERVICE._serialized_start=263
  _SLASERVICE._serialized_end=330
# @@protoc_insertion_point(module_scope)
