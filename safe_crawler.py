#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全的爬虫模式
使用更保守的策略避免被封IP
"""

import requests
import json
import time
import random
import logging
from fake_useragent import UserAgent
from crawl_songs import SongCrawler

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SafeCrawler(SongCrawler):
    def __init__(self, max_workers=1):
        # 不使用代理，使用单线程
        super().__init__(max_workers=max_workers, use_proxy=False)
        self.request_delay = 2.0  # 增加请求间隔
        self.ua_list = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
    
    def get_page_content(self, url, max_retries=5):
        """安全的页面获取方法"""
        for attempt in range(max_retries):
            try:
                # 随机延时
                delay = self.request_delay + random.uniform(0, 2)
                time.sleep(delay)
                
                # 随机User-Agent
                headers = {
                    'User-Agent': random.choice(self.ua_list),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                    'DNT': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                }
                
                # 创建新的session避免连接复用
                session = requests.Session()
                session.headers.update(headers)
                
                response = session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                logger.info(f"成功获取页面: {url}")
                return response.text
                
            except Exception as e:
                logger.error(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {url} - {e}")
                
                if attempt < max_retries - 1:
                    # 指数退避
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.info(f"等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"所有重试都失败，放弃页面: {url}")
                    return None
        
        return None
    
    def crawl_singer_songs(self, singer_info):
        """安全的歌手歌曲爬取"""
        logger.info(f"开始安全爬取歌手: {singer_info['name']} (ID: {singer_info['id']})")
        singer_songs = []
        
        try:
            # 获取歌手的最大页数
            max_page = self.find_max_page_for_singer(singer_info)
            logger.info(f"歌手 {singer_info['name']} 共有 {max_page} 页")
            
            # 串行处理每一页
            for page_num in range(1, max_page + 1):
                page_url = f"{self.base_url}/singer/{singer_info['id']}/{page_num}.html"
                html_content = self.get_page_content(page_url)
                
                if html_content:
                    songs = self.parse_songs_from_singer_page(html_content, singer_info)
                    singer_songs.extend(songs)
                    logger.info(f"歌手 {singer_info['name']} 第 {page_num}/{max_page} 页: 找到 {len(songs)} 首歌曲")
                else:
                    logger.warning(f"跳过失败的页面: {page_url}")
                
                # 页面间额外延时
                if page_num < max_page:
                    extra_delay = random.uniform(1, 3)
                    logger.info(f"页面间休息 {extra_delay:.1f} 秒...")
                    time.sleep(extra_delay)
            
            logger.info(f"歌手 {singer_info['name']} 完成，共获取 {len(singer_songs)} 首歌曲")
            self.songs_data.extend(singer_songs)
            return singer_songs
            
        except Exception as e:
            logger.error(f"爬取歌手 {singer_info['name']} 失败: {e}")
            return []
    
    def crawl_all_songs_safe(self, singers_file="singers_33ve.json", limit=None):
        """安全模式爬取所有歌手的歌曲"""
        logger.info("开始安全模式爬取歌手歌曲...")
        
        # 读取歌手数据
        try:
            with open(singers_file, 'r', encoding='utf-8') as f:
                singers_data = json.load(f)
            singers = singers_data['singers']
            if limit:
                singers = singers[:limit]
            logger.info(f"读取到 {len(singers)} 个歌手，将使用安全模式串行处理")
        except Exception as e:
            logger.error(f"读取歌手文件失败: {e}")
            return
        
        # 串行处理每个歌手
        for i, singer in enumerate(singers):
            logger.info(f"进度: {i+1}/{len(singers)} - 开始处理歌手: {singer['name']}")
            
            try:
                self.crawl_singer_songs(singer)
                
                # 歌手间休息
                if i < len(singers) - 1:
                    rest_time = random.uniform(5, 10)
                    logger.info(f"歌手间休息 {rest_time:.1f} 秒...")
                    time.sleep(rest_time)
                    
            except Exception as e:
                logger.error(f"处理歌手 {singer['name']} 时出错: {e}")
                continue
        
        logger.info(f"安全模式爬取完成，总共获取 {len(self.songs_data)} 首歌曲")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='安全模式爬虫')
    parser.add_argument('--limit-singers', type=int, default=10, 
                       help='限制爬取的歌手数量')
    
    args = parser.parse_args()
    
    crawler = SafeCrawler()
    
    try:
        # 开始爬取
        crawler.crawl_all_songs_safe(limit=args.limit_singers)
        
        # 保存结果
        crawler.save_to_file("songs_safe_33ve.json")
        
        print(f"\n安全模式爬取完成！")
        print(f"总计获取歌曲: {len(crawler.songs_data)} 首")
        print(f"数据已保存到: songs_safe_33ve.json")
        
    except KeyboardInterrupt:
        logger.info("用户中断了爬取过程")
        if crawler.songs_data:
            logger.info("保存已获取的数据...")
            crawler.save_to_file("songs_safe_33ve.json")
    except Exception as e:
        logger.error(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
