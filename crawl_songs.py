#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
33ve音乐网站歌曲爬虫脚本
用于获取歌手的所有歌曲信息
"""

import requests
import json
import time
import re
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from fake_useragent import UserAgent
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pathlib import Path
from proxy_pool import ProxyPool
from datetime import datetime, timedelta
from config import SAFE_MODE_ENABLED, SINGER_CRAWL_CACHE_DAYS
from config import SAFE_MODE_ENABLED

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SongCrawler:
    def __init__(self, max_workers=8, use_proxy=True):
        self.base_url = "https://www.33ve.com"
        self.session = requests.Session()
        self.ua = UserAgent()
        self.songs_data = []
        self.safe_mode = bool(SAFE_MODE_ENABLED)
        # 安全模式下强制单线程
        self.max_workers = 1 if self.safe_mode else max_workers
        self.lock = threading.Lock()
        self.use_proxy = use_proxy
        self.proxy_pool = None
        # 爬取缓存（按歌手）
        self.cache_file = Path("crawl_cache.json")
        self.cache_lock = threading.Lock()
        self.cache = self._load_cache()
        self.cache_days = int(SINGER_CRAWL_CACHE_DAYS) if str(SINGER_CRAWL_CACHE_DAYS).isdigit() else 28
        
        # 初始化代理池
        if use_proxy:
            self.proxy_pool = ProxyPool()
            # 尝试加载已保存的代理
            if not self.proxy_pool.load_proxies():
                logger.info("未找到已保存的代理，开始获取新代理...")
                self.proxy_pool.refresh_proxies()
                self.proxy_pool.save_proxies()
            
            status = self.proxy_pool.get_status()
            logger.info(f"代理池状态: {status['working_proxies']} 个可用代理")
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def _load_cache(self):
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
        return {}

    def _save_cache(self):
        try:
            with self.cache_lock:
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")

    def _get_last_crawl_ts(self, singer_id: str):
        try:
            entry = self.cache.get('singer_last_crawl', {}).get(str(singer_id))
            if entry:
                return datetime.fromisoformat(entry)
        except Exception:
            return None
        return None

    def _is_recent(self, singer_id: str) -> bool:
        last_dt = self._get_last_crawl_ts(singer_id)
        if not last_dt:
            return False
        return datetime.now() - last_dt < timedelta(days=self.cache_days)

    def _update_last_crawl(self, singer_id: str):
        with self.cache_lock:
            if 'singer_last_crawl' not in self.cache:
                self.cache['singer_last_crawl'] = {}
            self.cache['singer_last_crawl'][str(singer_id)] = datetime.now().isoformat()
        self._save_cache()
    
    def get_page_content(self, url, max_retries=3):
        """获取页面内容，支持代理池"""
        for attempt in range(max_retries):
            proxy_dict = None
            current_proxy = None
            
            # 获取代理
            if self.use_proxy and self.proxy_pool:
                current_proxy = self.proxy_pool.get_random_proxy()
                if current_proxy:
                    proxy_dict = self.proxy_pool.get_proxy_dict(current_proxy)
            
            try:
                # 随机化User-Agent
                headers = self.session.headers.copy()
                headers['User-Agent'] = self.ua.random
                
                response = self.session.get(
                    url, 
                    proxies=proxy_dict,
                    timeout=30,
                    headers=headers
                )
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                # 请求成功，返回内容
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.error(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {url} - {e}")
                
                # 如果使用了代理且请求失败，标记代理失效
                if current_proxy and self.proxy_pool:
                    self.proxy_pool.mark_proxy_failed(current_proxy)
                
                if attempt < max_retries - 1:
                    # 安全模式下增加退避等待
                    sleep_sec = (2 ** attempt) * (2.0 if self.safe_mode else 1.0)
                    time.sleep(sleep_sec)
                else:
                    return None
        return None
    
    def parse_songs_from_singer_page(self, html_content, singer_info):
        """从歌手页面解析歌曲信息，直接获取下载链接"""
        soup = BeautifulSoup(html_content, 'html.parser')
        songs_dict = {}  # 使用字典去重，key为歌曲ID
        
        # 查找歌曲链接 - 基于你提供的格式: /mp3/xxxxx.html
        song_links = soup.find_all('a', href=re.compile(r'/mp3/[a-f0-9]+\.html'))
        
        for link in song_links:
            href = link.get('href')
            if href:
                # 提取歌曲ID
                match = re.search(r'/mp3/([a-f0-9]+)\.html', href)
                if match:
                    song_id = match.group(1)
                    song_title = link.get_text(strip=True)
                    full_url = urljoin(self.base_url, href)
                    
                    # 直接生成下载链接
                    download_url = f"{self.base_url}/plug/down.php?ac=music&id={song_id}"
                    
                    # 如果已存在该ID，选择标题更完整的版本
                    if song_id in songs_dict:
                        existing_title = songs_dict[song_id]['title']
                        # 如果新标题更长或现有标题为空，则更新
                        if len(song_title) > len(existing_title) or not existing_title:
                            songs_dict[song_id]['title'] = song_title
                    else:
                        song_info = {
                            'id': song_id,
                            'title': song_title,
                            'url': full_url,
                            'singer_id': singer_info['id'],
                            'singer_name': singer_info['name'],
                            'download_url': download_url,
                            'download_id': song_id,
                            'file_size': None,
                            'duration': None
                        }
                        songs_dict[song_id] = song_info
        
        # 转换字典为列表，并过滤掉标题为空的歌曲
        songs = []
        for song_info in songs_dict.values():
            # 只保留有标题的歌曲
            if song_info['title'].strip():
                songs.append(song_info)
            else:
                logger.debug(f"跳过无标题歌曲: {song_info['id']}")
        
        return songs
    

    
    def find_max_page_for_singer(self, singer_info):
        """查找歌手的最大页数"""
        base_url = f"{self.base_url}/singer/{singer_info['id']}/1.html"
        html_content = self.get_page_content(base_url)
        if not html_content:
            return 1
        
        soup = BeautifulSoup(html_content, 'html.parser')
        max_page = 1
        
        # 查找分页链接
        page_links = soup.find_all('a', href=re.compile(rf"/singer/{singer_info['id']}/\d+\.html"))
        for link in page_links:
            href = link.get('href')
            if href:
                match = re.search(rf"/singer/{singer_info['id']}/(\d+)\.html", href)
                if match:
                    page_num = int(match.group(1))
                    max_page = max(max_page, page_num)
        
        # 检查分页导航
        pagination = soup.find('div', class_=['pagination', 'page', 'pager'])
        if pagination:
            page_nums = re.findall(r'\b(\d+)\b', pagination.get_text())
            if page_nums:
                try:
                    max_page = max(max_page, max(int(num) for num in page_nums if num.isdigit()))
                except:
                    pass
        
        return max_page
    
    def crawl_singer_songs(self, singer_info):
        """爬取单个歌手的所有歌曲"""
        logger.info(f"开始爬取歌手: {singer_info['name']} (ID: {singer_info['id']})")
        singer_songs = []
        
        try:
            # 缓存检查：4周内已爬过则跳过
            if self._is_recent(singer_info['id']):
                logger.info(f"跳过（4周内已爬）：{singer_info['name']} (ID: {singer_info['id']})")
                return []
            # 获取歌手的最大页数
            max_page = self.find_max_page_for_singer(singer_info)
            logger.info(f"歌手 {singer_info['name']} 共有 {max_page} 页")
            
            # 遍历所有页面
            for page_num in range(1, max_page + 1):
                page_url = f"{self.base_url}/singer/{singer_info['id']}/{page_num}.html"
                html_content = self.get_page_content(page_url)
                
                if html_content:
                    songs = self.parse_songs_from_singer_page(html_content, singer_info)
                    singer_songs.extend(songs)
                    logger.info(f"歌手 {singer_info['name']} 第 {page_num} 页: 找到 {len(songs)} 首歌曲")
                
                # 安全模式：更长间隔；否则保持较短
                time.sleep(1.0 if self.safe_mode else 0.1)
            
            # 下载链接已经在解析时直接生成，无需额外请求
            logger.info(f"歌手 {singer_info['name']} 的歌曲信息已完整获取")
            
            # 线程安全地添加到总列表
            with self.lock:
                self.songs_data.extend(singer_songs)
            
            logger.info(f"歌手 {singer_info['name']} 完成，共获取 {len(singer_songs)} 首歌曲")
            # 更新最后爬取时间
            self._update_last_crawl(singer_info['id'])
            return singer_songs
            
        except Exception as e:
            logger.error(f"爬取歌手 {singer_info['name']} 失败: {e}")
            # 失败不更新缓存时间
            return []
    
    def _merge_songs_into_file(self, songs_to_merge, filename="songs_33ve.json"):
        """将传入的歌曲列表合并写入到指定文件，按 id 去重并更新统计"""
        try:
            dest = Path(filename)
            existing = []
            if dest.exists():
                with open(dest, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                existing = data.get('songs', [])
            # 合并去重
            def sk(s):
                return s.get('id') or f"{s.get('singer_name')}::{s.get('title')}"
            id2song = {sk(s): s for s in existing}
            for s in songs_to_merge:
                id2song[sk(s)] = s
            final_songs = list(id2song.values())
            # 统计
            singer_stats = {}
            for s in final_songs:
                n = s.get('singer_name', '未知')
                singer_stats[n] = singer_stats.get(n, 0) + 1
            out = {
                'total_songs': len(final_songs),
                'total_singers': len(singer_stats),
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'singer_stats': singer_stats,
                'songs': final_songs
            }
            with open(dest, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            logger.info(f"已增量合并写入 {len(songs_to_merge)} 首到 {filename}，总计 {len(final_songs)} 首")
        except Exception as e:
            logger.error(f"增量合并写入失败: {e}")

    def crawl_all_songs(self, singers_file="singers_33ve.json", limit=None, output_file=None):
        """爬取歌手歌曲。若提供 output_file，将在每个歌手完成后增量落盘该文件。"""
        logger.info("开始爬取所有歌手的歌曲...")
        
        # 读取歌手数据
        try:
            with open(singers_file, 'r', encoding='utf-8') as f:
                singers_data = json.load(f)
            singers = singers_data['singers']
            if limit:
                singers = singers[:limit]
            logger.info(f"读取到 {len(singers)} 个歌手")
        except Exception as e:
            logger.error(f"读取歌手文件失败: {e}")
            return
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_singer = {
                executor.submit(self.crawl_singer_songs, singer): singer 
                for singer in singers
            }
            
            completed = 0
            for future in as_completed(future_to_singer):
                singer = future_to_singer[future]
                try:
                    result = future.result()
                    completed += 1
                    logger.info(f"进度: {completed}/{len(singers)} - 完成歌手: {singer['name']}")
                    # 增量写入
                    if output_file and result:
                        self._merge_songs_into_file(result, filename=output_file)
                except Exception as e:
                    logger.error(f"处理歌手 {singer['name']} 时出错: {e}")
        
        logger.info(f"所有歌手处理完成，总共获取 {len(self.songs_data)} 首歌曲")
    
    def save_to_file(self, filename="songs_33ve.json"):
        """保存歌曲数据到文件"""
        try:
            # 按歌手分组统计
            singer_stats = {}
            for song in self.songs_data:
                singer_name = song['singer_name']
                if singer_name not in singer_stats:
                    singer_stats[singer_name] = 0
                singer_stats[singer_name] += 1
            
            data = {
                'total_songs': len(self.songs_data),
                'total_singers': len(singer_stats),
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'singer_stats': singer_stats,
                'songs': self.songs_data
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"歌曲数据已保存到 {filename}")
            logger.info(f"总计歌曲数量: {len(self.songs_data)}")
            logger.info(f"涉及歌手数量: {len(singer_stats)}")
            
            # 显示前几首歌曲作为示例
            if self.songs_data:
                logger.info("前5首歌曲示例:")
                for i, song in enumerate(self.songs_data[:5]):
                    logger.info(f"  {i+1}. {song['singer_name']} - {song['title']}")
                    
        except Exception as e:
            logger.error(f"保存文件时出错: {e}")

def main():
    """主函数"""
    crawler = SongCrawler(max_workers=5, use_proxy=True)  # 使用代理时减少并发数
    
    try:
        # 开始爬取（限制前10个歌手用于测试）
        crawler.crawl_all_songs(limit=10)
        
        # 保存结果
        crawler.save_to_file()
        
        print(f"\n歌曲爬取完成！")
        print(f"总计获取歌曲: {len(crawler.songs_data)} 首")
        print(f"数据已保存到: songs_33ve.json")
        
    except KeyboardInterrupt:
        logger.info("用户中断了爬取过程")
        if crawler.songs_data:
            logger.info("保存已获取的数据...")
            crawler.save_to_file()
    except Exception as e:
        logger.error(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
