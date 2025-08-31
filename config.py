#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局配置加载器
优先从 config.json 读取配置，否则使用内置默认值
"""

import json
from pathlib import Path

_DEFAULTS = {
    "download_dir": "music_downloads",
    "download_limit": 20,
    "download_max_workers": 3,
    "safe_mode_enabled": False,
    "singer_crawl_cache_days": 28,
    "downloaded_cache_days": 180,
    "crawler_max_workers": 3,
    "proxy_enabled": True,
}


def _load_config_from_json() -> dict:
    config_path = Path("config.json")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            # 读取失败时走默认
            pass
    return {}


_USER_CONFIG = _load_config_from_json()


def get_config() -> dict:
    """返回合并后的配置字典"""
    merged = dict(_DEFAULTS)
    merged.update(_USER_CONFIG)
    return merged


# 常用配置项（便于直接导入使用）
DOWNLOAD_DIR = get_config().get("download_dir", _DEFAULTS["download_dir"])  # 下载目录
DOWNLOAD_LIMIT = get_config().get("download_limit", _DEFAULTS["download_limit"])  # 下载数量限制默认
DOWNLOAD_MAX_WORKERS = get_config().get("download_max_workers", _DEFAULTS["download_max_workers"])  # 下载线程数默认
SAFE_MODE_ENABLED = get_config().get("safe_mode_enabled", _DEFAULTS["safe_mode_enabled"])  # 安全模式开关
SINGER_CRAWL_CACHE_DAYS = get_config().get("singer_crawl_cache_days", _DEFAULTS["singer_crawl_cache_days"])  # 歌手爬取缓存天数
DOWNLOADED_CACHE_DAYS = get_config().get("downloaded_cache_days", _DEFAULTS["downloaded_cache_days"])  # 已下载歌曲索引缓存天数
CRAWLER_MAX_WORKERS = get_config().get("crawler_max_workers", _DEFAULTS["crawler_max_workers"])  # 歌曲爬取线程数默认
PROXY_ENABLED = get_config().get("proxy_enabled", _DEFAULTS["proxy_enabled"])  # 是否启用代理池默认


