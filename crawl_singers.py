#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
33ve音乐网站歌手ID爬虫脚本
用于获取所有歌手的ID信息
"""

import requests
import json
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from fake_useragent import UserAgent
import logging
import argparse
from config import SAFE_MODE_ENABLED

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SingerCrawler:
    def __init__(self):
        self.base_url = "https://www.33ve.com"
        self.singers_index_url = "https://www.33ve.com/singers/index/index/{}.html"
        self.session = requests.Session()
        self.ua = UserAgent()
        self.singers_data = []
        self.safe_mode = bool(SAFE_MODE_ENABLED)
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def get_page_content(self, url, max_retries=3):
        """获取页面内容"""
        for attempt in range(max_retries):
            try:
                # 安全模式：请求前延时
                if self.safe_mode:
                    time.sleep(1.0)
                logger.info(f"正在访问: {url} (尝试 {attempt + 1}/{max_retries})")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response.text
            except requests.exceptions.RequestException as e:
                logger.error(f"请求失败: {e}")
                if attempt < max_retries - 1:
                    # 安全模式下加倍退避
                    backoff = (2 ** attempt) * (2.0 if self.safe_mode else 1.0)
                    time.sleep(backoff)
                else:
                    raise
        return None
    
    def parse_singers_from_page(self, html_content):
        """从页面内容中解析歌手信息"""
        soup = BeautifulSoup(html_content, 'html.parser')
        singers = []
        
        # 查找歌手链接的模式，基于你提供的URL格式: /singer/805063/1.html
        singer_links = soup.find_all('a', href=re.compile(r'/singer/\d+/\d+\.html'))
        
        for link in singer_links:
            href = link.get('href')
            if href:
                # 提取歌手ID
                match = re.search(r'/singer/(\d+)/\d+\.html', href)
                if match:
                    singer_id = match.group(1)
                    singer_name = link.get_text(strip=True)
                    full_url = urljoin(self.base_url, href)
                    
                    singer_info = {
                        'id': singer_id,
                        'name': singer_name,
                        'url': full_url,
                        'base_url': f"{self.base_url}/singer/{singer_id}"
                    }
                    singers.append(singer_info)
                    logger.info(f"找到歌手: {singer_name} (ID: {singer_id})")
        
        # 也查找其他可能的歌手链接格式
        other_links = soup.find_all('a', href=re.compile(r'/singer'))
        for link in other_links:
            href = link.get('href')
            if href and '/singer/' in href:
                # 尝试提取ID
                id_match = re.search(r'/singer/(\d+)', href)
                if id_match:
                    singer_id = id_match.group(1)
                    singer_name = link.get_text(strip=True)
                    
                    # 检查是否已经添加过
                    if not any(s['id'] == singer_id for s in singers):
                        full_url = urljoin(self.base_url, href)
                        singer_info = {
                            'id': singer_id,
                            'name': singer_name,
                            'url': full_url,
                            'base_url': f"{self.base_url}/singer/{singer_id}"
                        }
                        singers.append(singer_info)
                        logger.info(f"找到额外歌手: {singer_name} (ID: {singer_id})")
        
        return singers
    
    def find_max_page(self, html_content):
        """查找最大页数"""
        soup = BeautifulSoup(html_content, 'html.parser')
        max_page = 1
        
        # 查找分页链接
        page_links = soup.find_all('a', href=re.compile(r'/singers/index/index/\d+\.html'))
        for link in page_links:
            href = link.get('href')
            if href:
                match = re.search(r'/singers/index/index/(\d+)\.html', href)
                if match:
                    page_num = int(match.group(1))
                    max_page = max(max_page, page_num)
        
        # 也检查分页导航
        pagination = soup.find('div', class_=['pagination', 'page', 'pager'])
        if pagination:
            page_nums = re.findall(r'\b(\d+)\b', pagination.get_text())
            if page_nums:
                max_page = max(max_page, max(int(num) for num in page_nums if num.isdigit()))
        
        return max_page
    
    def crawl_all_singers(self, name_filter: str | list[str] | None = None):
        """爬取歌手信息。支持单个或多个名称关键词，任一匹配即保留。"""
        logger.info("开始爬取歌手信息...")
        filters: list[str] = []
        if name_filter:
            if isinstance(name_filter, list):
                filters = [f.lower() for f in name_filter if f]
                logger.info(f"按名称筛选: {filters}")
            else:
                filters = [name_filter.lower()]
                logger.info(f"按名称筛选: '{name_filter}'")
        
        # 首先访问第一页来确定总页数
        first_page_url = self.singers_index_url.format(1)
        try:
            first_page_content = self.get_page_content(first_page_url)
            if not first_page_content:
                logger.error("无法获取第一页内容")
                return
            
            # 查找最大页数
            max_page = self.find_max_page(first_page_content)
            logger.info(f"检测到最大页数: {max_page}")
            
            # 解析第一页的歌手
            singers = self.parse_singers_from_page(first_page_content)
            if filters:
                singers = [s for s in singers if any(f in (s['name'] or '').lower() for f in filters)]
            self.singers_data.extend(singers)
            
            # 遍历剩余页面
            for page_num in range(2, max_page + 1):
                try:
                    page_url = self.singers_index_url.format(page_num)
                    page_content = self.get_page_content(page_url)
                    
                    if page_content:
                        singers = self.parse_singers_from_page(page_content)
                        if filters:
                            singers = [s for s in singers if any(f in (s['name'] or '').lower() for f in filters)]
                        self.singers_data.extend(singers)
                        logger.info(f"第 {page_num} 页完成，累计歌手数: {len(self.singers_data)}")
                    
                    # 添加延时避免被封（安全模式更慢）
                    time.sleep(2.0 if self.safe_mode else 1.0)
                    
                except Exception as e:
                    logger.error(f"处理第 {page_num} 页时出错: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"爬取过程中出错: {e}")
        
        # 去重处理
        unique_singers = {}
        for singer in self.singers_data:
            singer_id = singer['id']
            if singer_id not in unique_singers:
                unique_singers[singer_id] = singer
            else:
                # 如果名字更完整，则更新
                if len(singer['name']) > len(unique_singers[singer_id]['name']):
                    unique_singers[singer_id] = singer
        
        self.singers_data = list(unique_singers.values())
        logger.info(f"去重后总歌手数: {len(self.singers_data)}")
    
    def save_to_file(self, filename="singers_33ve.json"):
        """保存歌手数据到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_singers': len(self.singers_data),
                    'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'singers': self.singers_data
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"歌手数据已保存到 {filename}")
            logger.info(f"总计歌手数量: {len(self.singers_data)}")
            
            # 显示前几个歌手作为示例
            if self.singers_data:
                logger.info("前5个歌手示例:")
                for i, singer in enumerate(self.singers_data[:5]):
                    logger.info(f"  {i+1}. {singer['name']} (ID: {singer['id']})")
                    
        except Exception as e:
            logger.error(f"保存文件时出错: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='爬取歌手信息')
    parser.add_argument('--name', type=str, help='仅爬取名称包含该关键词的歌手（大小写不敏感）')
    args = parser.parse_args()

    crawler = SingerCrawler()
    try:
        crawler.crawl_all_singers(name_filter=args.name)
        crawler.save_to_file()
        print(f"\n爬取完成！")
        print(f"总计获取歌手: {len(crawler.singers_data)} 个")
        print(f"数据已保存到: singers_33ve.json")
    except KeyboardInterrupt:
        logger.info("用户中断了爬取过程")
        if crawler.singers_data:
            logger.info("保存已获取的数据...")
            crawler.save_to_file()
    except Exception as e:
        logger.error(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
