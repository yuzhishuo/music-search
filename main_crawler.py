#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
33ve音乐网站完整爬虫系统
整合歌手爬取、歌曲爬取和下载功能
"""

import argparse
import json
import logging
import time
from pathlib import Path

from crawl_singers import SingerCrawler
from crawl_songs import SongCrawler
from download_songs import SongDownloader
from config import DOWNLOAD_DIR

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MusicCrawlerManager:
    def __init__(self):
        self.singers_file = "singers_33ve.json"
        self.songs_file = "songs_33ve.json"
        self.download_dir = DOWNLOAD_DIR
    
    def _merge_songs_into_file(self, new_songs):
        """将新抓取的歌曲合并进 self.songs_file，按 id 去重并更新统计，返回合并后总数"""
        try:
            existing_songs = []
            dest_path = Path(self.songs_file)
            if dest_path.exists():
                with open(dest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                existing_songs = data.get('songs', [])
            # 合并去重
            def song_key(s):
                return s.get('id') or f"{s.get('singer_name')}::{s.get('title')}"
            id_to_song = {song_key(s): s for s in existing_songs}
            for s in new_songs:
                id_to_song[song_key(s)] = s
            final_songs = list(id_to_song.values())
            # 统计
            singer_stats = {}
            for s in final_songs:
                name = s.get('singer_name', '未知')
                singer_stats[name] = singer_stats.get(name, 0) + 1
            out = {
                'total_songs': len(final_songs),
                'total_singers': len(singer_stats),
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'singer_stats': singer_stats,
                'songs': final_songs
            }
            with open(dest_path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            return len(final_songs)
        except Exception as e:
            logger.error(f"合并歌曲文件失败: {e}")
            # 退化为直接覆盖写入新数据
            try:
                with open(self.songs_file, 'w', encoding='utf-8') as f:
                    json.dump({'total_songs': len(new_songs), 'total_singers': 0, 'singer_stats': {}, 'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'), 'songs': new_songs}, f, ensure_ascii=False, indent=2)
                return len(new_songs)
            except Exception:
                return 0
    
    def crawl_singers(self, name_filters: list[str] | None = None):
        """爬取歌手；支持名称关键词筛选（支持多关键词，任一匹配）"""
        logger.info("=== 开始爬取歌手信息 ===")
        crawler = SingerCrawler()
        crawler.crawl_all_singers(name_filter=name_filters)
        crawler.save_to_file(self.singers_file)
        return len(crawler.singers_data)
    
    def crawl_songs(self, limit_singers=None, max_workers=5, use_proxy=True, name_filters: list[str] | None = None):
        """爬取歌曲信息"""
        logger.info("=== 开始爬取歌曲信息 ===")
        
        # 检查歌手文件是否存在
        if not Path(self.singers_file).exists():
            logger.error(f"歌手文件 {self.singers_file} 不存在，请先运行歌手爬取")
            return 0
        
        # 如提供名称筛选，则基于歌手文件过滤后写入临时文件供歌曲爬虫使用
        source_file = self.singers_file
        temp_file = None
        if (name_filters and len(name_filters) > 0) or limit_singers:
            try:
                with open(self.singers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                singers = data.get('singers', [])
                if name_filters:
                    keys = [k.lower() for k in name_filters if k]
                    singers = [s for s in singers if any(k in (s.get('name') or '').lower() for k in keys)]
                    logger.info(f"按名称筛选 {name_filters} 后剩余 {len(singers)} 个歌手")
                if limit_singers:
                    singers = singers[:limit_singers]
                    logger.info(f"限制爬取歌手数量为 {len(singers)} 个")
                temp_file = Path('temp_singers_filtered.json')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump({'total_singers': len(singers), 'singers': singers}, f, ensure_ascii=False, indent=2)
                source_file = str(temp_file)
            except Exception as e:
                logger.error(f"准备筛选歌手列表失败，将使用原始文件: {e}")
                source_file = self.singers_file
        
        crawler = SongCrawler(max_workers=max_workers, use_proxy=use_proxy)
        # 传入筛选后的文件；在每个歌手完成后增量落盘
        crawler.crawl_all_songs(source_file, limit=None, output_file=self.songs_file)
        # 额外保障：最终再合并一次（处理并发期间遗漏）
        merged_total = self._merge_songs_into_file(crawler.songs_data)
        # 清理临时文件
        if temp_file and Path(temp_file).exists():
            try:
                Path(temp_file).unlink()
            except Exception:
                pass
        return merged_total
    
    def download_songs(self, limit_songs=None, filter_singer=None, max_workers=5):
        """下载歌曲文件"""
        logger.info("=== 开始下载歌曲文件 ===")
        
        # 检查歌曲文件是否存在
        if not Path(self.songs_file).exists():
            logger.error(f"歌曲文件 {self.songs_file} 不存在，请先运行歌曲爬取")
            return 0, 0
        
        downloader = SongDownloader(self.download_dir, max_workers=max_workers)
        downloader.download_from_json(
            self.songs_file, 
            limit=limit_songs, 
            filter_singer=filter_singer
        )
        return downloader.downloaded_count, downloader.failed_count
    
    def run_full_pipeline(self, limit_singers=5, limit_songs=20, max_workers=5, use_proxy=True):
        """运行完整的爬取流程"""
        logger.info("=== 开始完整爬取流程 ===")
        start_time = time.time()
        
        try:
            # 步骤1: 爬取歌手（如果文件不存在）
            if not Path(self.singers_file).exists():
                logger.info("步骤1: 爬取歌手信息")
                singers_count = self.crawl_singers()
                logger.info(f"✓ 歌手爬取完成，共获取 {singers_count} 个歌手")
            else:
                logger.info("步骤1: 歌手文件已存在，跳过爬取")
                with open(self.singers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    singers_count = data['total_singers']
                    logger.info(f"✓ 读取到 {singers_count} 个歌手")
            
            # 步骤2: 爬取歌曲
            logger.info("步骤2: 爬取歌曲信息")
            songs_count = self.crawl_songs(limit_singers=limit_singers, max_workers=max_workers, use_proxy=use_proxy)
            logger.info(f"✓ 歌曲爬取完成，共获取 {songs_count} 首歌曲")
            
            # 步骤3: 下载歌曲
            logger.info("步骤3: 下载歌曲文件")
            downloaded, failed = self.download_songs(limit_songs=limit_songs, max_workers=max_workers)
            logger.info(f"✓ 歌曲下载完成，成功 {downloaded} 首，失败 {failed} 首")
            
            # 总结
            end_time = time.time()
            duration = end_time - start_time
            logger.info("=== 完整流程完成 ===")
            logger.info(f"总耗时: {duration:.2f} 秒")
            logger.info(f"歌手数量: {singers_count}")
            logger.info(f"歌曲数量: {songs_count}")
            logger.info(f"下载成功: {downloaded}")
            logger.info(f"下载失败: {failed}")
            
            return {
                'duration': duration,
                'singers_count': singers_count,
                'songs_count': songs_count,
                'downloaded': downloaded,
                'failed': failed
            }
            
        except Exception as e:
            logger.error(f"完整流程执行出错: {e}")
            return None
    
    def show_statistics(self):
        """显示统计信息"""
        print("\n=== 数据统计 ===")
        
        # 歌手统计
        if Path(self.singers_file).exists():
            with open(self.singers_file, 'r', encoding='utf-8') as f:
                singers_data = json.load(f)
            print(f"歌手数量: {singers_data['total_singers']}")
            print(f"歌手文件: {self.singers_file}")
        else:
            print("歌手文件: 不存在")
        
        # 歌曲统计
        if Path(self.songs_file).exists():
            with open(self.songs_file, 'r', encoding='utf-8') as f:
                songs_data = json.load(f)
            print(f"歌曲数量: {songs_data['total_songs']}")
            print(f"涉及歌手: {songs_data['total_singers']}")
            print(f"歌曲文件: {self.songs_file}")
        else:
            print("歌曲文件: 不存在")
        
        # 下载统计
        # download_path = Path(self.download_dir)
        # if download_path.exists():
        #     music_files = list(download_path.rglob("*.mp3")) + \
        #                  list(download_path.rglob("*.wav")) + \
        #                  list(download_path.rglob("*.flac")) + \
        #                  list(download_path.rglob("*.m4a"))
        #     total_size = sum(f.stat().st_size for f in music_files)
        #     print(f"已下载文件: {len(music_files)} 个")
        #     print(f"总文件大小: {total_size / (1024*1024):.2f} MB")
        #     print(f"下载目录: {download_path}")
        # else:
        #     print("下载目录: 不存在")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='33ve音乐网站爬虫系统')
    parser.add_argument('--mode', choices=['singers', 'songs', 'download', 'full', 'stats'], 
                       default='full', help='运行模式')
    parser.add_argument('--limit-singers', type=int, default=5, 
                       help='限制爬取的歌手数量（用于测试）')
    parser.add_argument('--singer-name', type=str, help='按名称筛选歌手；可用分号分隔多个关键词，例如 "李宗盛;罗大佑"')
    parser.add_argument('--limit-songs', type=int, default=20, 
                       help='限制下载的歌曲数量（用于测试）')
    parser.add_argument('--filter-singer', type=str, 
                       help='只下载特定歌手的歌曲')
    parser.add_argument('--max-workers', type=int, default=5, 
                       help='最大并发线程数')
    parser.add_argument('--no-proxy', action='store_true', 
                       help='不使用代理池')
    
    args = parser.parse_args()
    
    manager = MusicCrawlerManager()
    
    try:
        if args.mode == 'singers':
            # 只爬取歌手
            name_filters = None
            if args.singer_name:
                name_filters = [t.strip() for t in args.singer_name.split(';') if t.strip()]
            count = manager.crawl_singers(name_filters=name_filters)
            print(f"\n爬取完成！共获取 {count} 个歌手")
            
        elif args.mode == 'songs':
            # 只爬取歌曲
            name_filters = None
            if args.singer_name:
                name_filters = [t.strip() for t in args.singer_name.split(';') if t.strip()]
            count = manager.crawl_songs(
                limit_singers=args.limit_singers,
                max_workers=args.max_workers,
                use_proxy=not args.no_proxy,
                name_filters=name_filters
            )
            print(f"\n爬取完成！共获取 {count} 首歌曲")
            
        elif args.mode == 'download':
            # 只下载歌曲
            downloaded, failed = manager.download_songs(
                limit_songs=args.limit_songs,
                filter_singer=args.filter_singer,
                max_workers=args.max_workers
            )
            print(f"\n下载完成！成功 {downloaded} 首，失败 {failed} 首")
            
        elif args.mode == 'full':
            # 完整流程
            result = manager.run_full_pipeline(
                limit_singers=args.limit_singers,
                limit_songs=args.limit_songs,
                max_workers=args.max_workers,
                use_proxy=not args.no_proxy
            )
            if result:
                print(f"\n完整流程完成！")
                print(f"总耗时: {result['duration']:.2f} 秒")
                print(f"歌手: {result['singers_count']} 个")
                print(f"歌曲: {result['songs_count']} 首")
                print(f"下载成功: {result['downloaded']} 首")
                print(f"下载失败: {result['failed']} 首")
            
        elif args.mode == 'stats':
            # 显示统计信息
            manager.show_statistics()
        
    except KeyboardInterrupt:
        logger.info("用户中断了程序")
    except Exception as e:
        logger.error(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
