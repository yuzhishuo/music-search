#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速开始脚本
一键运行爬虫系统的核心功能
"""

import os
import json
from pathlib import Path

def check_environment():
    """检查环境和依赖"""
    print("🔍 检查环境...")
    
    # 检查Python版本
    import sys
    if sys.version_info < (3, 8):
        print("❌ Python版本过低，需要3.8+")
        return False
    
    # 检查必要的包
    required_packages = ['requests', 'beautifulsoup4', 'fake_useragent', 'tqdm']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    print("✅ 环境检查通过")
    return True

def check_data_files():
    """检查数据文件状态"""
    print("\n📁 检查数据文件...")
    
    singers_file = Path("singers_33ve.json")
    songs_file = Path("songs_33ve.json")
    
    status = {
        'singers_exists': singers_file.exists(),
        'songs_exists': songs_file.exists(),
        'singers_count': 0,
        'songs_count': 0
    }
    
    if status['singers_exists']:
        try:
            with open(singers_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                status['singers_count'] = data.get('total_singers', 0)
            print(f"✅ 歌手文件存在: {status['singers_count']} 个歌手")
        except:
            print("⚠️  歌手文件存在但格式有误")
    else:
        print("❌ 歌手文件不存在")
    
    if status['songs_exists']:
        try:
            with open(songs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                status['songs_count'] = data.get('total_songs', 0)
            print(f"✅ 歌曲文件存在: {status['songs_count']} 首歌曲")
        except:
            print("⚠️  歌曲文件存在但格式有误")
    else:
        print("❌ 歌曲文件不存在")
    
    return status

def quick_demo():
    """快速演示"""
    print("\n🚀 开始快速演示...")
    print("这将爬取3个歌手的歌曲信息，然后下载5首歌曲")
    
    confirm = input("是否继续? (y/n): ").lower().strip()
    if confirm != 'y':
        print("演示取消")
        return
    
    try:
        from main_crawler import MusicCrawlerManager
        
        manager = MusicCrawlerManager()
        
        # 1. 爬取歌曲信息
        print("\n📝 步骤1: 爬取歌曲信息...")
        songs_count = manager.crawl_songs(
            limit_singers=3,
            max_workers=2,
            use_proxy=False  # 暂时不使用代理避免复杂性
        )
        print(f"✅ 获取到 {songs_count} 首歌曲")
        
        if songs_count > 0:
            # 2. 下载歌曲
            print("\n📥 步骤2: 下载歌曲文件...")
            downloaded, failed = manager.download_songs(
                limit_songs=5,
                max_workers=2
            )
            print(f"✅ 下载完成 - 成功: {downloaded} 首，失败: {failed} 首")
            
            # 3. 显示统计
            print("\n📊 步骤3: 数据统计...")
            manager.show_statistics()
        
        print("\n🎉 快速演示完成!")
        
    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
        print("可能的原因:")
        print("- 网络连接问题")
        print("- 目标网站访问限制")
        print("- 依赖包版本问题")

def show_usage_guide():
    """显示使用指南"""
    print("\n📖 使用指南:")
    print("""
基本命令:
1. 查看统计: python main_crawler.py --mode stats
2. 爬取歌曲: python main_crawler.py --mode songs --limit-singers 10
3. 下载歌曲: python main_crawler.py --mode download --limit-songs 20
4. 完整流程: python main_crawler.py --mode full --limit-singers 5 --limit-songs 10

高级选项:
- 指定歌手: --filter-singer "周杰伦"
- 调整并发: --max-workers 3
- 禁用代理: --no-proxy

安全模式:
python safe_crawler.py --limit-singers 5

更多示例:
python example_usage.py
""")

def main():
    """主函数"""
    print("🎵 33ve音乐爬虫系统 - 快速开始")
    print("=" * 50)
    
    # 检查环境
    if not check_environment():
        return
    
    # 检查数据文件
    data_status = check_data_files()
    
    # 显示选项
    print("\n📋 可用选项:")
    print("1. 快速演示 (推荐新用户)")
    print("2. 查看使用指南")
    print("3. 退出")
    
    choice = input("\n请选择 (1-3): ").strip()
    
    if choice == '1':
        quick_demo()
    elif choice == '2':
        show_usage_guide()
    elif choice == '3':
        print("👋 再见!")
    else:
        print("❌ 无效选择")

if __name__ == "__main__":
    main()

