#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理IP池管理器
用于避免IP被封，支持多种代理源
"""

import requests
import json
import time
import random
import logging
import threading
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from fake_useragent import UserAgent

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProxyPool:
    def __init__(self):
        self.proxies = []
        self.working_proxies = []
        self.failed_proxies = set()
        self.lock = threading.Lock()
        self.ua = UserAgent()
        self.test_url = "https://www.33ve.com/"
        self.test_timeout = 10
        
    def get_free_proxies(self):
        """获取免费代理IP"""
        proxy_sources = [
            self._get_proxies_from_proxylist,
            self._get_proxies_from_freeproxy,
            self._get_proxies_from_proxyrotator,
        ]
        
        all_proxies = []
        for source in proxy_sources:
            try:
                proxies = source()
                all_proxies.extend(proxies)
                logger.info(f"从 {source.__name__} 获取到 {len(proxies)} 个代理")
            except Exception as e:
                logger.error(f"从 {source.__name__} 获取代理失败: {e}")
        
        # 去重
        unique_proxies = []
        seen = set()
        for proxy in all_proxies:
            proxy_key = f"{proxy['ip']}:{proxy['port']}"
            if proxy_key not in seen:
                seen.add(proxy_key)
                unique_proxies.append(proxy)
        
        logger.info(f"总共获取到 {len(unique_proxies)} 个唯一代理")
        return unique_proxies
    
    def _get_proxies_from_proxylist(self):
        """从proxylist.geonode.com获取代理"""
        proxies = []
        try:
            # 获取HTTP代理
            url = "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            for item in data.get('data', []):
                if item.get('protocols', []):
                    proxy = {
                        'ip': item['ip'],
                        'port': item['port'],
                        'protocol': 'http',
                        'country': item.get('country', 'Unknown'),
                        'speed': item.get('speed', 0)
                    }
                    proxies.append(proxy)
        except Exception as e:
            logger.error(f"从proxylist获取代理失败: {e}")
        
        return proxies[:50]  # 限制数量
    
    def _get_proxies_from_freeproxy(self):
        """从free-proxy-list.net获取代理"""
        proxies = []
        try:
            # 这里可以添加其他免费代理源的API
            # 由于很多免费代理API不稳定，这里提供一个框架
            pass
        except Exception as e:
            logger.error(f"从freeproxy获取代理失败: {e}")
        
        return proxies
    
    def _get_proxies_from_proxyrotator(self):
        """从其他代理源获取"""
        proxies = []
        # 可以添加更多代理源
        return proxies
    
    def add_manual_proxies(self, proxy_list: List[str]):
        """手动添加代理列表
        Args:
            proxy_list: 代理列表，格式如 ['ip:port', 'ip:port']
        """
        for proxy_str in proxy_list:
            if ':' in proxy_str:
                ip, port = proxy_str.split(':', 1)
                proxy = {
                    'ip': ip.strip(),
                    'port': int(port.strip()),
                    'protocol': 'http',
                    'country': 'Manual',
                    'speed': 0
                }
                self.proxies.append(proxy)
        
        logger.info(f"手动添加了 {len(proxy_list)} 个代理")
    
    def load_manual_proxies(self, filename="manual_proxies.txt"):
        """从文件加载手动代理"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            proxy_list = []
            for line in lines:
                line = line.strip()
                # 跳过空行和注释行
                if line and not line.startswith('#'):
                    proxy_list.append(line)
            
            if proxy_list:
                self.add_manual_proxies(proxy_list)
                logger.info(f"从 {filename} 加载了 {len(proxy_list)} 个手动代理")
                return True
            else:
                logger.info(f"文件 {filename} 中没有找到有效代理")
                return False
                
        except FileNotFoundError:
            logger.info(f"代理文件 {filename} 不存在")
            return False
        except Exception as e:
            logger.error(f"加载手动代理失败: {e}")
            return False
    
    def test_proxy(self, proxy: Dict) -> bool:
        """测试单个代理是否可用"""
        proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        try:
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=self.test_timeout,
                headers={'User-Agent': self.ua.random}
            )
            
            if response.status_code == 200:
                logger.info(f"代理可用: {proxy['ip']}:{proxy['port']}")
                return True
            else:
                logger.debug(f"代理返回状态码 {response.status_code}: {proxy['ip']}:{proxy['port']}")
                return False
                
        except Exception as e:
            logger.debug(f"代理测试失败: {proxy['ip']}:{proxy['port']} - {e}")
            return False
    
    def test_all_proxies(self, max_workers=20):
        """并发测试所有代理"""
        logger.info(f"开始测试 {len(self.proxies)} 个代理...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {
                executor.submit(self.test_proxy, proxy): proxy 
                for proxy in self.proxies
            }
            
            working_count = 0
            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    if future.result():
                        with self.lock:
                            self.working_proxies.append(proxy)
                            working_count += 1
                except Exception as e:
                    logger.error(f"测试代理时出错: {proxy['ip']}:{proxy['port']} - {e}")
        
        logger.info(f"测试完成，可用代理: {len(self.working_proxies)} 个")
        
        # 按速度排序（如果有速度信息）
        self.working_proxies.sort(key=lambda x: x.get('speed', 0), reverse=True)
    
    def get_random_proxy(self) -> Optional[Dict]:
        """获取一个随机可用代理"""
        with self.lock:
            if not self.working_proxies:
                return None
            
            # 随机选择一个代理
            proxy = random.choice(self.working_proxies)
            return proxy
    
    def mark_proxy_failed(self, proxy: Dict):
        """标记代理失效"""
        proxy_key = f"{proxy['ip']}:{proxy['port']}"
        with self.lock:
            self.failed_proxies.add(proxy_key)
            # 从工作代理列表中移除
            self.working_proxies = [
                p for p in self.working_proxies 
                if f"{p['ip']}:{p['port']}" != proxy_key
            ]
        
        logger.warning(f"代理已标记为失效: {proxy['ip']}:{proxy['port']}")
    
    def get_proxy_dict(self, proxy: Dict) -> Dict[str, str]:
        """将代理转换为requests可用的格式"""
        proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def refresh_proxies(self):
        """刷新代理池"""
        logger.info("开始刷新代理池...")
        
        # 清空当前代理
        self.proxies.clear()
        self.working_proxies.clear()
        self.failed_proxies.clear()
        
        # 优先加载手动代理
        manual_loaded = self.load_manual_proxies()
        
        # 如果没有手动代理，尝试获取免费代理
        if not manual_loaded:
            logger.info("没有手动代理，尝试获取免费代理...")
            new_proxies = self.get_free_proxies()
            self.proxies.extend(new_proxies)
        
        # 测试代理
        if self.proxies:
            self.test_all_proxies()
        else:
            logger.warning("没有找到任何代理，将使用直连模式")
        
        logger.info(f"代理池刷新完成，可用代理: {len(self.working_proxies)} 个")
    
    def save_proxies(self, filename="working_proxies.json"):
        """保存可用代理到文件"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.working_proxies, f, ensure_ascii=False, indent=2)
            logger.info(f"可用代理已保存到 {filename}")
        except Exception as e:
            logger.error(f"保存代理失败: {e}")
    
    def load_proxies(self, filename="working_proxies.json"):
        """从文件加载代理"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                proxies = json.load(f)
            
            self.working_proxies.extend(proxies)
            logger.info(f"从 {filename} 加载了 {len(proxies)} 个代理")
            return True
        except Exception as e:
            logger.error(f"加载代理失败: {e}")
            return False
    
    def get_status(self) -> Dict:
        """获取代理池状态"""
        return {
            'total_proxies': len(self.proxies),
            'working_proxies': len(self.working_proxies),
            'failed_proxies': len(self.failed_proxies),
            'success_rate': len(self.working_proxies) / len(self.proxies) * 100 if self.proxies else 0
        }

def main():
    """测试代理池"""
    pool = ProxyPool()
    
    # 可以手动添加一些已知的代理
    manual_proxies = [
        # "127.0.0.1:8080",  # 示例：本地代理
        # "proxy.example.com:3128",  # 示例：其他代理
    ]
    
    if manual_proxies:
        pool.add_manual_proxies(manual_proxies)
    
    # 获取免费代理
    pool.refresh_proxies()
    
    # 保存可用代理
    pool.save_proxies()
    
    # 显示状态
    status = pool.get_status()
    print(f"\n=== 代理池状态 ===")
    print(f"总代理数: {status['total_proxies']}")
    print(f"可用代理: {status['working_proxies']}")
    print(f"失效代理: {status['failed_proxies']}")
    print(f"成功率: {status['success_rate']:.1f}%")
    
    # 测试获取随机代理
    for i in range(3):
        proxy = pool.get_random_proxy()
        if proxy:
            print(f"随机代理 {i+1}: {proxy['ip']}:{proxy['port']} ({proxy['country']})")
        else:
            print(f"随机代理 {i+1}: 无可用代理")

if __name__ == "__main__":
    main()
