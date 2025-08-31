#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
33ve音乐网站歌曲下载器
用于下载歌曲文件
"""

import requests
import json
import time
import os
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
from fake_useragent import UserAgent
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from tqdm import tqdm
from config import DOWNLOAD_DIR, DOWNLOAD_MAX_WORKERS, SAFE_MODE_ENABLED
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SongDownloader:
    def __init__(self, download_dir=None, max_workers=None, overwrite_existing=False):
        # 如果未指定则使用配置中的默认目录
        resolved_dir = download_dir or DOWNLOAD_DIR
        self.download_dir = Path(resolved_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.ua = UserAgent()
        self.safe_mode = bool(SAFE_MODE_ENABLED)
        # 安全模式下强制单线程
        self.max_workers = 1 if self.safe_mode else (
            max_workers if isinstance(max_workers, int) and max_workers > 0 else DOWNLOAD_MAX_WORKERS
        )
        self.lock = threading.Lock()
        self.downloaded_count = 0
        self.failed_count = 0
        self.overwrite_existing = overwrite_existing
        # 每首歌请求前的延时（安全模式下更长）
        self.per_request_delay_sec = 1.5 if self.safe_mode else 0.0
        # 已下载缓存索引
        self.downloaded_index_file = Path("downloaded_cache.json")
        self.downloaded_index = self._load_downloaded_index()
        try:
            from config import DOWNLOADED_CACHE_DAYS
            self.downloaded_cache_days = int(DOWNLOADED_CACHE_DAYS) if str(DOWNLOADED_CACHE_DAYS).isdigit() else 180
        except Exception:
            self.downloaded_cache_days = 180
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://www.33ve.com/',
        })
    
    def sanitize_filename(self, filename):
        """清理文件名，移除非法字符"""
        # 移除或替换非法字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        # 限制文件名长度
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename.strip()
    
    def get_file_extension_from_url(self, url):
        """从URL或响应中获取文件扩展名"""
        try:
            # 先尝试从URL获取
            parsed = urlparse(url)
            path = unquote(parsed.path)
            if '.' in path:
                ext = path.split('.')[-1].lower()
                if ext in ['mp3', 'wav', 'flac', 'm4a', 'aac']:
                    return f'.{ext}'
            
            # 如果URL没有扩展名，发送HEAD请求获取Content-Type
            response = self.session.head(url, timeout=10)
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'audio/mpeg' in content_type or 'audio/mp3' in content_type:
                return '.mp3'
            elif 'audio/wav' in content_type:
                return '.wav'
            elif 'audio/flac' in content_type:
                return '.flac'
            elif 'audio/mp4' in content_type or 'audio/m4a' in content_type:
                return '.m4a'
            elif 'audio/aac' in content_type:
                return '.aac'
            
        except Exception as e:
            logger.debug(f"获取文件扩展名失败: {e}")
        
        # 默认返回mp3
        return '.mp3'
    
    def _build_file_stem(self, song_info):
        safe_title = self.sanitize_filename(song_info['title'])
        safe_singer = self.sanitize_filename(song_info['singer_name'])
        return f"{safe_singer} - {safe_title}"

    def is_song_already_downloaded(self, song_info):
        """基于歌手目录和文件名（忽略扩展名差异）判断是否已下载"""
        # 先看缓存
        try:
            key = song_info.get('id') or f"{song_info.get('singer_name')}::{song_info.get('title')}"
            entry = self.downloaded_index.get('songs', {}).get(key)
            if entry:
                ts = datetime.fromisoformat(entry.get('ts')) if entry.get('ts') else None
                if ts and datetime.now() - ts < timedelta(days=self.downloaded_cache_days):
                    return True
        except Exception:
            pass
        # 回退文件系统
        try:
            singer_dir = self.download_dir / self.sanitize_filename(song_info['singer_name'])
            stem = self._build_file_stem(song_info)
            possible_exts = ['.mp3', '.wav', '.flac', '.m4a', '.aac']
            for ext in possible_exts:
                if (singer_dir / f"{stem}{ext}").exists():
                    # 发现文件则更新缓存
                    self._mark_downloaded(song_info)
                    return True
            return False
        except Exception:
            return False

    def _load_downloaded_index(self):
        try:
            if self.downloaded_index_file.exists():
                with open(self.downloaded_index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {"songs": {}}
        except Exception:
            pass
        return {"songs": {}}

    def _save_downloaded_index(self):
        try:
            with open(self.downloaded_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.downloaded_index, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _mark_downloaded(self, song_info):
        try:
            if 'songs' not in self.downloaded_index:
                self.downloaded_index['songs'] = {}
            key = song_info.get('id') or f"{song_info.get('singer_name')}::{song_info.get('title')}"
            self.downloaded_index['songs'][key] = {
                'ts': datetime.now().isoformat(),
                'singer': song_info.get('singer_name'),
                'title': song_info.get('title')
            }
            self._save_downloaded_index()
        except Exception:
            pass

    def download_song(self, song_info, max_retries=3):
        """下载单首歌曲"""
        if not song_info.get('download_url'):
            logger.warning(f"歌曲没有下载链接: {song_info['singer_name']} - {song_info['title']}")
            return False
        
        try:
            # 创建歌手文件夹
            singer_dir = self.download_dir / self.sanitize_filename(song_info['singer_name'])
            singer_dir.mkdir(exist_ok=True)
            
            # 生成文件名
            safe_title = self.sanitize_filename(song_info['title'])
            safe_singer = self.sanitize_filename(song_info['singer_name'])
            
            # 先获取文件扩展名
            file_ext = self.get_file_extension_from_url(song_info['download_url'])
            filename = f"{safe_singer} - {safe_title}{file_ext}"
            filepath = singer_dir / filename
            
            # 检查文件是否已存在
            if filepath.exists():
                if self.overwrite_existing:
                    try:
                        filepath.unlink(missing_ok=True)
                        logger.info(f"覆盖已存在文件: {filename}")
                    except Exception as e:
                        logger.error(f"无法删除已存在文件以覆盖: {filename} - {e}")
                        with self.lock:
                            self.failed_count += 1
                        return False
                else:
                    logger.info(f"文件已存在，跳过: {filename}")
                    with self.lock:
                        self.downloaded_count += 1
                    return True
            
            # 下载文件
            for attempt in range(max_retries):
                try:
                    logger.info(f"开始下载: {song_info['singer_name']} - {song_info['title']}")
                    # 安全模式：请求前延时
                    if self.per_request_delay_sec > 0:
                        time.sleep(self.per_request_delay_sec)
                    
                    response = self.session.get(
                        song_info['download_url'], 
                        timeout=60,
                        stream=True
                    )
                    response.raise_for_status()
                    
                    # 获取文件大小
                    total_size = int(response.headers.get('content-length', 0))
                    
                    # 写入文件
                    with open(filepath, 'wb') as f:
                        if total_size > 0:
                            with tqdm(
                                total=total_size,
                                unit='B',
                                unit_scale=True,
                                desc=filename[:50],
                                leave=False
                            ) as pbar:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        pbar.update(len(chunk))
                        else:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                    
                    # 验证文件是否下载完整
                    if filepath.stat().st_size > 0:
                        logger.info(f"下载成功: {filename} ({filepath.stat().st_size} bytes)")
                        with self.lock:
                            self.downloaded_count += 1
                        self._mark_downloaded(song_info)
                        return True
                    else:
                        logger.error(f"下载的文件为空: {filename}")
                        filepath.unlink(missing_ok=True)
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"下载失败 (尝试 {attempt + 1}/{max_retries}): {filename} - {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                    else:
                        with self.lock:
                            self.failed_count += 1
                        return False
                except Exception as e:
                    logger.error(f"下载过程中出错: {filename} - {e}")
                    if filepath.exists():
                        filepath.unlink(missing_ok=True)
                    with self.lock:
                        self.failed_count += 1
                    return False
            
        except Exception as e:
            logger.error(f"下载歌曲失败: {song_info['singer_name']} - {song_info['title']} - {e}")
            with self.lock:
                self.failed_count += 1
            return False
        
        return False
    
    def download_from_json(self, songs_file="songs_33ve.json", limit=None, filter_singer=None):
        """从JSON文件下载歌曲"""
        try:
            with open(songs_file, 'r', encoding='utf-8') as f:
                songs_data = json.load(f)
            
            songs = songs_data['songs']
            
            # 过滤特定歌手
            if filter_singer:
                songs = [song for song in songs if filter_singer.lower() in song['singer_name'].lower()]
                logger.info(f"过滤歌手 '{filter_singer}' 后，共 {len(songs)} 首歌曲")
            
            # 先排除已下载的，再按限制取需要下载的新歌曲
            not_downloaded = [s for s in songs if not self.is_song_already_downloaded(s)]
            if limit:
                songs = not_downloaded[:limit]
                logger.info(f"限制下载新歌曲数量为 {limit} 首（已排除已存在文件）")
            else:
                songs = not_downloaded
                logger.info(f"准备下载 {len(songs)} 首新歌曲（已排除已存在文件）")
            
            logger.info(f"准备下载 {len(songs)} 首歌曲")
            
            # 使用线程池下载
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_song = {
                    executor.submit(self.download_song, song): song 
                    for song in songs
                }
                
                # 显示总体进度
                with tqdm(total=len(songs), desc="总体进度") as pbar:
                    for future in as_completed(future_to_song):
                        song = future_to_song[future]
                        try:
                            result = future.result()
                            pbar.update(1)
                            pbar.set_postfix({
                                '成功': self.downloaded_count,
                                '失败': self.failed_count
                            })
                        except Exception as e:
                            logger.error(f"处理歌曲时出错: {song['singer_name']} - {song['title']} - {e}")
                            pbar.update(1)
            
            logger.info(f"下载完成！成功: {self.downloaded_count}, 失败: {self.failed_count}")
            
        except Exception as e:
            logger.error(f"读取歌曲文件失败: {e}")
    
    def download_songs_list(self, songs_list, limit=None):
        """下载歌曲列表；数量限制仅作用于未下载过的歌曲"""
        # 先排除已下载的
        to_download = [s for s in songs_list if not self.is_song_already_downloaded(s)]
        if limit:
            to_download = to_download[:limit]
            logger.info(f"限制下载新歌曲数量为 {limit} 首（已排除已存在文件）")
        logger.info(f"准备下载 {len(to_download)} 首歌曲")
        
        if not to_download:
            logger.info("没有需要下载的新歌曲")
            return
        
        # 使用线程池下载
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_song = {
                executor.submit(self.download_song, song): song 
                for song in to_download
            }
            
            # 显示总体进度
            with tqdm(total=len(to_download), desc="下载进度") as pbar:
                for future in as_completed(future_to_song):
                    song = future_to_song[future]
                    try:
                        result = future.result()
                        pbar.update(1)
                        pbar.set_postfix({
                            '成功': self.downloaded_count,
                            '失败': self.failed_count
                        })
                    except Exception as e:
                        logger.error(f"处理歌曲时出错: {song['singer_name']} - {song['title']} - {e}")
                        pbar.update(1)
        
        logger.info(f"下载完成！成功: {self.downloaded_count}, 失败: {self.failed_count}")

def main():
    """主函数"""
    downloader = SongDownloader(max_workers=5)  # 使用5个线程提高下载速度
    
    try:
        # 从JSON文件下载（限制前20首用于测试）
        downloader.download_from_json(limit=20)
        
        print(f"\n下载完成！")
        print(f"成功下载: {downloader.downloaded_count} 首")
        print(f"下载失败: {downloader.failed_count} 首")
        print(f"文件保存在: {downloader.download_dir}")
        
    except KeyboardInterrupt:
        logger.info("用户中断了下载过程")
    except Exception as e:
        logger.error(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
