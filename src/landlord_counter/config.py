"""全局配置：从环境变量/配置文件读取，密钥不硬编码。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_dotenv() -> None:
    """加载项目根 .env 到环境变量（覆盖旧 shell 残留，.env 是项目配置源）。

    让 `uv run landlord-counter` / CLI 工具无需手动 source 即可读到 VLM 等配置。
    注意：会覆盖同名已存在的环境变量——若想临时换模型，直接改 .env 即可。
    """
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("\"'")
            if key:
                os.environ[key] = value  # .env 为准，覆盖 shell 残留旧值
    except OSError:
        pass


_load_dotenv()


@dataclass
class ScreenConfig:
    """屏幕与ROI配置（像素坐标，手机横屏/竖屏可调）"""
    adb_serial: str = field(default_factory=lambda: os.getenv("ADB_SERIAL", os.getenv("AGENT_ADB_SERIAL", "")))  # 多设备时建议显式指定
    screen_scale: float = 1.0  # 截图缩放系数
    # 各识别区域 ROI: (x1, y1, x2, y2)，默认竖屏 1080x2400 比例
    hand_roi: tuple = (0.0, 0.78, 1.0, 1.0)  # 自己手牌区（归一化坐标）
    played_roi: tuple = (0.15, 0.30, 0.85, 0.70)  # 出牌区（归一化坐标）
    poll_interval: float = 1.0  # 轮询间隔秒


@dataclass
class VisionConfig:
    """识别层配置"""
    # 模板匹配
    template_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "assets" / "card_templates"
    )
    match_threshold: float = 0.80  # 模板匹配置信度阈值
    # 游戏视觉适配包（哪个 App 的画面）：doudizhu_wishday 等，见 profiles.py
    profile_name: str = field(default_factory=lambda: os.getenv("GAME_PROFILE", "doudizhu_wishday"))
    # VLM 直读（模板对重度重叠无效时的主链路，需 API key）
    vlm_api_base: str = os.getenv("VLM_API_BASE", "")
    vlm_api_key: str = os.getenv("VLM_API_KEY", "")
    vlm_model: str = os.getenv("VLM_MODEL", "glm-4v-plus")

    def vlm_available(self) -> bool:
        return bool(self.vlm_api_base and self.vlm_api_key)


@dataclass
class LLMConfig:
    """大模型推理配置（可选，用于对手牌型分析）"""
    enabled: bool = os.getenv("LLM_ENABLED", "0") == "1"
    api_base: str = os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1")
    api_key: str = os.getenv("LLM_API_KEY", "")
    model: str = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    temperature: float = 0.3


@dataclass
class AppConfig:
    screen: ScreenConfig = field(default_factory=ScreenConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


def load_config() -> AppConfig:
    return AppConfig()
