from pydantic import BaseModel, ConfigDict, Field


class AgentReport(BaseModel):
    """System snapshot an agent is allowed to send. Extra fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    hostname: str = Field(default="", max_length=255)
    os_name: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=64)
    kernel_version: str | None = Field(default=None, max_length=128)
    cpu_cores: int | None = Field(default=None, ge=1, le=1024)
    cpu_percent: float = Field(default=0, ge=0, le=100)
    memory_total_bytes: int = Field(default=0, ge=0)
    memory_used_bytes: int = Field(default=0, ge=0)
    memory_percent: float = Field(default=0, ge=0, le=100)
    disk_total_bytes: int = Field(default=0, ge=0)
    disk_percent: float = Field(default=0, ge=0, le=100)
    net_rx_bytes: int = Field(default=0, ge=0)
    net_tx_bytes: int = Field(default=0, ge=0)
    load_1: float | None = None
    load_5: float | None = None
    load_15: float | None = None
    process_count: int | None = Field(default=None, ge=0)
    version: str | None = Field(default=None, max_length=32)
