#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用示例脚本
展示如何使用爬虫系统的各种功能
"""

import os
import time
from main_crawler import MusicCrawlerManager

def example_basic_usage():
    """基础使用示例"""
    print("=== 基础使用示例 ===")
    
    manager = MusicCrawlerManager()
    
    # 1. 查看当前数据统计
    print("1. 当前数据统计:")
    manager.show_statistics()
    
    # 2. 小规模测试爬取歌曲
    print("\n2. 测试爬取3个歌手的歌曲:")
    songs_count = manager.crawl_songs(
        limit_singers=3, 
        max_workers=2,  # 使用较少的并发数
        use_proxy=False  # 暂时不使用代理
    )
    print(f"获取到 {songs_count} 首歌曲")
    
    # 3. 下载少量歌曲测试
    print("\n3. 测试下载5首歌曲:")
    downloaded, failed = manager.download_songs(
        limit_songs=5,
        max_workers=2
    )
    print(f"下载成功: {downloaded} 首，失败: {failed} 首")

def example_specific_singer():
    """特定歌手示例"""
    print("=== 特定歌手下载示例 ===")
    
    manager = MusicCrawlerManager()
    
    # 下载特定歌手的歌曲
    singer_name = "周杰伦"  # 可以修改为其他歌手
    print(f"下载歌手: {singer_name}")
    
    downloaded, failed = manager.download_songs(
        limit_songs=10,  # 限制数量
        filter_singer=singer_name,
        max_workers=2
    )
    print(f"下载完成 - 成功: {downloaded} 首，失败: {failed} 首")

def example_safe_mode():
    """安全模式示例"""
    print("=== 安全模式示例 ===")
    
    from safe_crawler import SafeCrawler
    
    # 使用安全模式爬取
    crawler = SafeCrawler()
    
    print("使用安全模式爬取2个歌手...")
    crawler.crawl_all_songs_safe(limit=2)
    
    # 保存结果
    crawler.save_to_file("songs_safe_example.json")
    print(f"安全模式完成，获取 {len(crawler.songs_data)} 首歌曲")

def example_batch_processing():
    """批量处理示例"""
    print("=== 批量处理示例 ===")
    
    manager = MusicCrawlerManager()
    
    # 分批处理歌手，避免一次性处理太多
    batch_size = 5
    total_singers = 20
    
    for batch_start in range(0, total_singers, batch_size):
        batch_end = min(batch_start + batch_size, total_singers)
        print(f"\n处理第 {batch_start//batch_size + 1} 批: 歌手 {batch_start+1}-{batch_end}")
        
        # 读取歌手数据并选择批次
        import json
        with open('singers_33ve.json', 'r', encoding='utf-8') as f:
            singers_data = json.load(f)
        
        batch_singers = singers_data['singers'][batch_start:batch_end]
        
        # 保存批次歌手数据
        batch_file = f"singers_batch_{batch_start//batch_size + 1}.json"
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_singers': len(batch_singers),
                'singers': batch_singers
            }, f, ensure_ascii=False, indent=2)
        
        # 爬取这一批歌手的歌曲
        songs_count = manager.crawl_songs(
            limit_singers=batch_size,
            max_workers=2,
            use_proxy=False
        )
        
        print(f"批次 {batch_start//batch_size + 1} 完成: {songs_count} 首歌曲")
        
        # 批次间休息
        if batch_end < total_singers:
            print("批次间休息30秒...")
            time.sleep(30)

def main():
    """主函数 - 选择运行哪个示例"""
    examples = {
        '1': ('基础使用示例', example_basic_usage),
        '2': ('特定歌手示例', example_specific_singer),
        '3': ('安全模式示例', example_safe_mode),
        '4': ('批量处理示例', example_batch_processing),
    }
    
    print("请选择要运行的示例:")
    for key, (name, _) in examples.items():
        print(f"{key}. {name}")
    
    choice = input("\n请输入选择 (1-4): ").strip()
    
    if choice in examples:
        name, func = examples[choice]
        print(f"\n开始运行: {name}")
        print("=" * 50)
        
        try:
            func()
            print("\n示例运行完成!")
        except KeyboardInterrupt:
            print("\n用户中断了示例")
        except Exception as e:
            print(f"\n示例运行出错: {e}")
    else:
        print("无效选择!")

if __name__ == "__main__":
    main()

