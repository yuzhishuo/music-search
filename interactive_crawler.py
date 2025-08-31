#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式音乐爬虫界面
提供用户友好的交互式操作界面
"""

import os
import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Optional

from main_crawler import MusicCrawlerManager
from crawl_songs import SongCrawler
from download_songs import SongDownloader
from config import DOWNLOAD_DIR, DOWNLOAD_LIMIT, DOWNLOAD_MAX_WORKERS, CRAWLER_MAX_WORKERS, PROXY_ENABLED

class InteractiveCrawler:
    def __init__(self):
        self.manager = MusicCrawlerManager()
        self.singers_data = []
        self.load_singers_data()
    
    def load_singers_data(self):
        """加载歌手数据"""
        singers_file = Path("singers_33ve.json")
        if singers_file.exists():
            try:
                with open(singers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.singers_data = data.get('singers', [])
                print(f"✅ 已加载 {len(self.singers_data)} 个歌手数据")
            except Exception as e:
                print(f"❌ 加载歌手数据失败: {e}")
        else:
            print("⚠️  歌手数据文件不存在，部分功能可能不可用")
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """打印头部信息"""
        print("🎵" + "=" * 60 + "🎵")
        print("        33ve音乐爬虫系统 - 交互式界面")
        print("🎵" + "=" * 60 + "🎵")
        print()
    
    def print_menu(self):
        """打印主菜单"""
        menu_items = [
            "1. 📊 查看系统状态",
            "2. 👥 搜索歌手",
            "3. 🎵 爬取指定歌手歌曲",
            "4. 📥 下载歌曲",
            "5. 🔍 批量爬取歌手",
            "6. ⚙️  系统设置",
            "7. 📖 帮助信息",
            "8. 🚪 退出系统"
        ]
        
        print("📋 主菜单:")
        print("-" * 40)
        for item in menu_items:
            print(f"   {item}")
        print("-" * 40)
    
    def get_user_choice(self, prompt="请选择操作", valid_choices=None):
        """获取用户选择"""
        while True:
            try:
                choice = input(f"\n{prompt}: ").strip()
                if valid_choices and choice not in valid_choices:
                    print(f"❌ 无效选择，请输入: {', '.join(valid_choices)}")
                    continue
                return choice
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，退出系统")
                sys.exit(0)
    
    def search_singers(self, query=""):
        """搜索歌手"""
        if not self.singers_data:
            print("❌ 没有歌手数据，请先爬取歌手信息")
            return []
        
        if not query:
            query = input("🔍 请输入歌手名称关键词: ").strip()
        
        if not query:
            return []
        
        # 搜索匹配的歌手
        matches = []
        query_lower = query.lower()
        
        for singer in self.singers_data:
            if query_lower in singer['name'].lower():
                matches.append(singer)
        
        return matches
    
    def display_singers(self, singers: List[Dict], title="搜索结果"):
        """显示歌手列表"""
        if not singers:
            print("❌ 没有找到匹配的歌手")
            return
        
        print(f"\n📋 {title} (共 {len(singers)} 个):")
        print("-" * 50)
        for i, singer in enumerate(singers[:20], 1):  # 最多显示20个
            print(f"{i:2d}. {singer['name']} (ID: {singer['id']})")
        
        if len(singers) > 20:
            print(f"... 还有 {len(singers) - 20} 个结果未显示")
        print("-" * 50)
    
    def select_singer(self, singers: List[Dict]) -> Optional[Dict]:
        """选择歌手"""
        if not singers:
            return None
        
        if len(singers) == 1:
            confirm = self.get_user_choice(
                f"确认选择歌手 '{singers[0]['name']}' 吗? (y/n)", 
                ['y', 'n', 'Y', 'N']
            )
            return singers[0] if confirm.lower() == 'y' else None
        
        while True:
            try:
                choice = input(f"\n请选择歌手编号 (1-{min(len(singers), 20)}) 或输入 'q' 返回: ").strip()
                
                if choice.lower() == 'q':
                    return None
                
                index = int(choice) - 1
                if 0 <= index < min(len(singers), 20):
                    return singers[index]
                else:
                    print(f"❌ 请输入 1-{min(len(singers), 20)} 之间的数字")
            except ValueError:
                print("❌ 请输入有效的数字")
    
    def _merge_songs_into_main_file(self, new_songs: List[Dict], main_file: str = "songs_33ve.json"):
        """将新抓取的歌曲合并进主 songs 文件，按 id 去重并更新统计"""
        try:
            main_path = Path(main_file)
            merged_songs = []
            if main_path.exists():
                with open(main_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                merged_songs = data.get('songs', [])
            # 根据 id 去重合并
            id_to_song = {s.get('id') or f"{s.get('singer_name')}::{s.get('title')}": s for s in merged_songs}
            for s in new_songs:
                sid = s.get('id') or f"{s.get('singer_name')}::{s.get('title')}"
                id_to_song[sid] = s
            final_songs = list(id_to_song.values())
            # 统计
            singer_stats = {}
            for song in final_songs:
                name = song.get('singer_name', '未知')
                singer_stats[name] = singer_stats.get(name, 0) + 1
            data = {
                'total_songs': len(final_songs),
                'total_singers': len(singer_stats),
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'singer_stats': singer_stats,
                'songs': final_songs
            }
            with open(main_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return len(final_songs)
        except Exception as e:
            print(f"❌ 合并歌曲到 {main_file} 失败: {e}")
            return None

    def crawl_singer_by_name(self, singer_name: str, interactive: bool = True) -> Optional[str]:
        """根据名称搜索并爬取该歌手的歌曲，合并进 songs 文件。返回确认的歌手名或 None。
        interactive=False 时自动选择最佳匹配（精确命中优先，其次第一项），不弹出交互选择。
        若本地 singer 列表无匹配，会先按名称关键词增量爬取歌手列表并合并至 singers_33ve.json。
        """
        try:
            name_key = singer_name.strip()
            def ensure_singer_in_list() -> List[Dict]:
                matches_local = self.search_singers(query=name_key)
                if matches_local:
                    return matches_local
                # 本地未命中：按名称关键词增量爬取歌手列表并合并
                try:
                    from crawl_singers import SingerCrawler
                    crawler = SingerCrawler()
                    crawler.crawl_all_singers(name_filter=name_key)
                    # 合并到 singers_33ve.json
                    singers_file = Path("singers_33ve.json")
                    existing = {}
                    if singers_file.exists():
                        with open(singers_file, 'r', encoding='utf-8') as f:
                            existing = json.load(f)
                    exist_list = existing.get('singers', []) if existing else []
                    id_set = {s.get('id') for s in exist_list}
                    for s in crawler.singers_data:
                        if s.get('id') not in id_set:
                            exist_list.append(s)
                            id_set.add(s.get('id'))
                    merged = {
                        'total_singers': len(exist_list),
                        'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'singers': exist_list
                    }
                    with open(singers_file, 'w', encoding='utf-8') as f:
                        json.dump(merged, f, ensure_ascii=False, indent=2)
                    # 重新加载内存中的 singer 列表
                    self.load_singers_data()
                except Exception as e:
                    print(f"❌ 增量爬取歌手列表失败: {e}")
                return self.search_singers(query=name_key)

            matches = ensure_singer_in_list()
            if not matches:
                print(f"❌ 未找到包含关键词 '{name_key}' 的歌手")
                return None

            if interactive:
                self.display_singers(matches, title=f"搜索 '{name_key}' 的结果")
                selected_singer = self.select_singer(matches)
                if not selected_singer:
                    print("❌ 未选择歌手")
                    return None
            else:
                # 自动选择：精确名称优先，否则取第一项
                exact = [m for m in matches if m.get('name') == name_key]
                selected_singer = exact[0] if exact else matches[0]

            print(f"\n✅ 已选择歌手: {selected_singer['name']}")
            # 使用配置
            use_proxy = bool(PROXY_ENABLED)
            max_workers = int(CRAWLER_MAX_WORKERS) if str(CRAWLER_MAX_WORKERS).isdigit() else 3
            temp_singers_file = "temp_singer.json"
            temp_data = {
                'total_singers': 1,
                'singers': [selected_singer]
            }
            with open(temp_singers_file, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, ensure_ascii=False, indent=2)
            try:
                crawler = SongCrawler(max_workers=max_workers, use_proxy=use_proxy)
                # 每个歌手单独爬取，直接合并落盘
                crawler.crawl_all_songs(temp_singers_file, limit=1, output_file="songs_33ve.json")
                if crawler.songs_data:
                    # 再次合并确保一致
                    self._merge_songs_into_main_file(crawler.songs_data, "songs_33ve.json")
                print(f"✅ 已更新歌曲库，新增/更新 {len(crawler.songs_data)} 首: {selected_singer['name']}")
                return selected_singer['name']
            finally:
                try:
                    os.remove(temp_singers_file)
                except Exception:
                    pass
        except Exception as e:
            print(f"❌ 爬取歌手 '{singer_name}' 失败: {e}")
            return None

    def crawl_specific_singer(self):
        """爬取指定歌手的歌曲"""
        print("\n🎵 爬取指定歌手歌曲")
        print("=" * 40)
        
        # 支持输入 '.' 查看已存在的歌手（从本地 songs_33ve.json 读取）
        query = input("🔍 请输入歌手名称关键词（输入 '.' 查看已存在的歌手）: ").strip()
        displayed_list = False
        if query == '.':
            existing_singers = self.get_existing_singers_with_ids("songs_33ve.json")
            if not existing_singers:
                print("❌ 本地暂无已下载的歌手信息")
                return
            self.display_singers(existing_singers, title="已存在的歌手")
            matches = existing_singers
            displayed_list = True
        else:
            # 正常关键词搜索（基于 singers_33ve.json）
            matches = self.search_singers(query=query)
        if not matches:
            return
        
        # 显示列表（若刚刚已显示，则不再重复显示）
        if not displayed_list:
            self.display_singers(matches)
        
        # 选择歌手
        selected_singer = self.select_singer(matches)
        if not selected_singer:
            print("❌ 未选择歌手")
            return
        
        print(f"\n✅ 已选择歌手: {selected_singer['name']}")
        
        # 获取爬取选项
        print("\n⚙️  爬取选项 (使用配置默认，可在 config.json 修改):")
        use_proxy = bool(PROXY_ENABLED)
        max_workers = int(CRAWLER_MAX_WORKERS) if str(CRAWLER_MAX_WORKERS).isdigit() else 3
        
        print(f"\n🚀 开始爬取歌手 '{selected_singer['name']}' 的歌曲...")
        print(f"配置: 代理={use_proxy}, 线程数={max_workers}")
        
        try:
            # 创建临时歌手文件
            temp_singers_file = "temp_singer.json"
            temp_data = {
                'total_singers': 1,
                'singers': [selected_singer]
            }
            
            with open(temp_singers_file, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, ensure_ascii=False, indent=2)
            
            # 爬取歌曲
            crawler = SongCrawler(max_workers=max_workers, use_proxy=use_proxy)
            crawler.crawl_all_songs(temp_singers_file, limit=1)
            
            # 将结果合并到主 songs 文件
            merged_total = self._merge_songs_into_main_file(crawler.songs_data, "songs_33ve.json")
            output_file = "songs_33ve.json"
            
            # 清理临时文件
            os.remove(temp_singers_file)
            
            print(f"\n✅ 爬取完成!")
            print(f"歌手: {selected_singer['name']}")
            print(f"歌曲数量: {len(crawler.songs_data)}")
            print(f"保存文件: {output_file}{' (合并)' if merged_total is not None else ''}")
            if merged_total is not None:
                print(f"合并后总歌曲数: {merged_total}")
            
            # 询问是否下载
            if crawler.songs_data:
                download = self.get_user_choice("是否立即下载这些歌曲? (y/n)", ['y', 'n', 'Y', 'N'])
                if download.lower() == 'y':
                    self.download_from_file(output_file)
            
        except Exception as e:
            print(f"❌ 爬取失败: {e}")
    
    def get_existing_singer_names(self, songs_file: str) -> List[str]:
        """从 songs 文件中读取已存的歌手名称列表"""
        try:
            with open(songs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            names = []
            stats = data.get('singer_stats')
            if isinstance(stats, dict):
                names = list(stats.keys())
            else:
                seen = set()
                for s in data.get('songs', []):
                    n = s.get('singer_name')
                    if n and n not in seen:
                        seen.add(n)
                names = sorted(list(seen))
            return sorted(names)
        except Exception as e:
            print(f"❌ 读取歌手列表失败: {e}")
            return []

    def get_existing_singers_with_ids(self, songs_file: str) -> List[Dict]:
        """从 songs 文件中读取已存歌手，返回包含 name 与伪 id 的列表（用于选择）"""
        try:
            with open(songs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            names = []
            stats = data.get('singer_stats')
            if isinstance(stats, dict):
                names = list(stats.keys())
            else:
                seen = set()
                for s in data.get('songs', []):
                    n = s.get('singer_name')
                    if n and n not in seen:
                        seen.add(n)
                names = sorted(list(seen))
            # 构造选择列表，id 使用名称本身（后续仅用于显示/选择）
            return [{ 'id': name, 'name': name, 'source': 'local' } for name in names]
        except Exception as e:
            print(f"❌ 读取本地歌手失败: {e}")
            return []

    def list_existing_singers(self, songs_file: str):
        """打印已存歌手名称（最多显示前100个）"""
        names = self.get_existing_singer_names(songs_file)
        if not names:
            print("❌ 无可用歌手列表")
            return
        print(f"\n📚 已存歌手（共 {len(names)} 个）：")
        print("-" * 50)
        max_show = min(len(names), 100)
        for i, name in enumerate(names[:max_show], 1):
            print(f"{i:3d}. {name}")
        if len(names) > max_show:
            print(f"... 还有 {len(names) - max_show} 个未显示")

    def download_from_file(self, songs_file=None):
        """从文件下载歌曲"""
        if not songs_file:
            songs_file = "songs_33ve.json"
        
        if not Path(songs_file).exists():
            print(f"❌ 歌曲文件 {songs_file} 不存在")
            return
        
        print(f"\n📥 从 {songs_file} 下载歌曲")
        print("=" * 40)
        
        # 使用配置默认：下载数量限制与下载线程数
        limit = DOWNLOAD_LIMIT
        max_workers = DOWNLOAD_MAX_WORKERS
        
        custom_dir = input(f"自定义下载目录 (可选，默认{DOWNLOAD_DIR}): ").strip() or None
        
        # 读取全部歌曲
        with open(songs_file, 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
        all_songs = songs_data.get('songs', [])
        
        # 模式选择：1 按歌手下载；2 按歌曲下载
        print("\n📦 下载模式：")
        print("1. 按歌手下载（选择歌手后下载其全部歌曲）")
        print("2. 按歌曲下载（跨歌手选择具体歌曲）")
        mode = self.get_user_choice("请选择模式", ['1', '2'])
        
        # 通用选择解析器
        def parse_selection(sel: str, max_n: int):
            if not sel or sel.lower() == 'all':
                return set(range(1, max_n + 1))
            picked = set()
            for token in sel.split(','):
                token = token.strip()
                if not token:
                    continue
                if '-' in token:
                    try:
                        a, b = token.split('-', 1)
                        a = int(a); b = int(b)
                        if a <= b:
                            for x in range(max(1, a), min(max_n, b) + 1):
                                picked.add(x)
                    except Exception:
                        continue
                else:
                    if token.isdigit():
                        x = int(token)
                        if 1 <= x <= max_n:
                            picked.add(x)
            return picked
        
        if mode == '1':
            # 按歌手下载
            singer_names = sorted({s.get('singer_name') for s in all_songs if s.get('singer_name')})
            print("\n👥 选择歌手：输入编号（逗号分隔），支持区间如 1-5；回车或 all 表示全部。")
            max_show_singers = min(len(singer_names), 200)
            for i, name in enumerate(singer_names[:max_show_singers], 1):
                print(f"{i:3d}. {name}")
            if len(singer_names) > max_show_singers:
                print(f"... 共 {len(singer_names)} 位歌手，已只显示前 {max_show_singers} 位")
            singer_sel = input("歌手选择（可输入歌手名触发自动爬取）: ").strip()
            # 解析选择：数字/区间 -> 按索引；其他文本 -> 作为歌手名先爬取并合并后立刻可下载
            tokens = [t.strip() for t in singer_sel.split(',') if t.strip()]
            numeric_part = []
            name_part = []
            for t in tokens:
                if t.isdigit() or ('-' in t and all(x.strip().isdigit() for x in t.split('-', 1))):
                    numeric_part.append(t)
                else:
                    name_part.append(t)
            singer_idx = parse_selection(','.join(numeric_part), max_show_singers) if numeric_part else set()
            # 对非数字输入先执行按名爬取
            added_names = []
            for name_token in name_part:
                added = self.crawl_singer_by_name(name_token, interactive=False)
                if added:
                    added_names.append(added)
            # 重新载入所有歌曲并刷新歌手列表（以包含新爬取的歌手）
            if added_names:
                with open(songs_file, 'r', encoding='utf-8') as f:
                    songs_data = json.load(f)
                all_songs = songs_data.get('songs', [])
                singer_names = sorted({s.get('singer_name') for s in all_songs if s.get('singer_name')})
                max_show_singers = min(len(singer_names), 200)
            # 生成最终的歌手选择：
            # - 若有编号选择，则以编号为主
            # - 若没有编号但有名称输入，则仅按名称选择
            # - 若二者都没有（直接回车/all），则选择全部
            selected_singers = []
            if singer_idx:
                selected_singers = [singer_names[i-1] for i in sorted(singer_idx)]
            if added_names:
                for nm in added_names:
                    if nm in singer_names and nm not in selected_singers:
                        selected_singers.append(nm)
            if not selected_singers:
                selected_singers = singer_names
            final_songs = [s for s in all_songs if s.get('singer_name') in selected_singers]
            # 使用与下载器一致的本地缓存过滤已下载
            downloader = SongDownloader(download_dir=custom_dir or DOWNLOAD_DIR, max_workers=max_workers, overwrite_existing=False)
            pending_songs = [s for s in final_songs if not downloader.is_song_already_downloaded(s)]
            skipped = len(final_songs) - len(pending_songs)
            if skipped > 0:
                print(f"🔎 已过滤已下载 {skipped} 首，待下载 {len(pending_songs)} 首")
            print(f"\n🚀 开始下载...")
            print(f"配置: 模式=按歌手, 限制={limit or '无限制'}, 线程数={max_workers}, 已选歌手={len(selected_singers)} 位, 目录={custom_dir or DOWNLOAD_DIR}")
            # 将选择结果交给下载器，数量限制仅作用于“未下载过”的歌曲
            downloader.download_songs_list(pending_songs, limit=limit)
        else:
            # 按歌曲下载
            # 先实例化下载器以复用本地缓存判定
            downloader = SongDownloader(download_dir=custom_dir or DOWNLOAD_DIR, max_workers=max_workers, overwrite_existing=False)
            songs_sorted = sorted(all_songs, key=lambda s: ((s.get('singer_name') or ''), (s.get('title') or '')))
            # 过滤已下载歌曲，仅展示未下载列表
            pending_sorted = [s for s in songs_sorted if not downloader.is_song_already_downloaded(s)]
            skipped = len(songs_sorted) - len(pending_sorted)
            if skipped > 0:
                print(f"🔎 已过滤已下载 {skipped} 首，仅显示待下载 {len(pending_sorted)} 首")
            print("\n🎵 选择歌曲：输入编号（逗号分隔），支持区间如 1-20；回车或 all 表示全部。")
            max_show_songs = min(len(pending_sorted), 500)
            for i, s in enumerate(pending_sorted[:max_show_songs], 1):
                print(f"{i:3d}. {s.get('singer_name')} - {s.get('title')}")
            if len(pending_sorted) > max_show_songs:
                print(f"... 共 {len(pending_sorted)} 首，已只显示前 {max_show_songs} 首")
            song_sel = input("歌曲选择: ").strip()
            song_idx = parse_selection(song_sel, max_show_songs)
            final_songs = [pending_sorted[i-1] for i in sorted(song_idx)] if song_idx else pending_sorted
            print(f"\n🚀 开始下载...")
            print(f"配置: 模式=按歌曲, 限制={limit or '无限制'}, 线程数={max_workers}, 已选歌曲={len(final_songs)} 首, 目录={custom_dir or DOWNLOAD_DIR}")
        
        try:
            # 将选择结果交给下载器，数量限制仅作用于“未下载过”的歌曲
            downloader.download_songs_list(final_songs, limit=limit)
            
            print(f"\n✅ 下载完成!")
            print(f"成功: {downloader.downloaded_count} 首")
            print(f"失败: {downloader.failed_count} 首")
            print(f"保存目录: {downloader.download_dir}")
            
        except Exception as e:
            print(f"❌ 下载失败: {e}")
    
    def batch_crawl_singers(self):
        """批量爬取歌手"""
        print("\n🔍 批量爬取歌手")
        print("=" * 40)
        
        if not self.singers_data:
            print("❌ 没有歌手数据")
            return
        
        # 获取爬取范围
        total_singers = len(self.singers_data)
        print(f"总歌手数: {total_singers}")
        
        start_str = input(f"起始位置 (1-{total_singers}, 默认1): ").strip()
        start = 1
        if start_str.isdigit():
            start = max(1, min(total_singers, int(start_str)))
        
        count_str = input("爬取数量 (默认10): ").strip()
        count = 10
        if count_str.isdigit():
            count = max(1, int(count_str))
        
        # 获取其他选项
        use_proxy = self.get_user_choice("是否使用代理? (y/n)", ['y', 'n', 'Y', 'N']).lower() == 'y'
        max_workers = 3
        
        print(f"\n🚀 开始批量爬取...")
        print(f"范围: {start} - {start + count - 1}")
        print(f"配置: 代理={use_proxy}, 线程数={max_workers}")
        
        try:
            songs_count = self.manager.crawl_songs(
                limit_singers=count,
                max_workers=max_workers,
                use_proxy=use_proxy
            )
            
            print(f"\n✅ 批量爬取完成!")
            print(f"处理歌手数: {count}")
            print(f"获取歌曲数: {songs_count}")
            
        except Exception as e:
            print(f"❌ 批量爬取失败: {e}")
    
    def show_system_status(self):
        """显示系统状态"""
        print("\n📊 系统状态")
        print("=" * 40)
        self.manager.show_statistics()
    
    
    
    def system_settings(self):
        """系统设置"""
        print("\n⚙️  系统设置")
        print("=" * 40)
        
        settings_menu = [
            "1. 查看代理状态",
            "2. 刷新代理池",
            "3. 清理临时文件",
            "4. 返回主菜单"
        ]
        
        for item in settings_menu:
            print(f"   {item}")
        
        choice = self.get_user_choice("请选择", ['1', '2', '3', '4'])
        
        if choice == '1':
            self.show_proxy_status()
        elif choice == '2':
            self.refresh_proxy_pool()
        elif choice == '3':
            self.clean_temp_files()
    
    def show_proxy_status(self):
        """显示代理状态"""
        print("\n🔄 代理池状态")
        print("-" * 30)
        
        try:
            from proxy_pool import ProxyPool
            pool = ProxyPool()
            
            if pool.load_proxies():
                status = pool.get_status()
                print(f"可用代理: {status['working_proxies']} 个")
                print(f"总代理: {status['total_proxies']} 个")
                print(f"成功率: {status['success_rate']:.1f}%")
            else:
                print("❌ 没有可用代理")
        except Exception as e:
            print(f"❌ 获取代理状态失败: {e}")
    
    def refresh_proxy_pool(self):
        """刷新代理池"""
        print("\n🔄 刷新代理池...")
        
        try:
            from proxy_pool import ProxyPool
            pool = ProxyPool()
            pool.refresh_proxies()
            pool.save_proxies()
            
            status = pool.get_status()
            print(f"✅ 代理池刷新完成")
            print(f"可用代理: {status['working_proxies']} 个")
        except Exception as e:
            print(f"❌ 刷新代理池失败: {e}")
    
    def clean_temp_files(self):
        """清理临时文件"""
        print("\n🧹 清理临时文件...")
        
        temp_patterns = ['temp_*.json', 'songs_*_*.json']
        cleaned_count = 0
        
        for pattern in temp_patterns:
            for file_path in Path('.').glob(pattern):
                try:
                    file_path.unlink()
                    cleaned_count += 1
                    print(f"删除: {file_path}")
                except Exception as e:
                    print(f"删除失败 {file_path}: {e}")
        
        print(f"✅ 清理完成，删除了 {cleaned_count} 个文件")
    
    def show_help(self):
        """显示帮助信息"""
        print("\n📖 帮助信息")
        print("=" * 40)
        help_text = """
🎵 功能说明:
1. 查看系统状态 - 显示已爬取的数据统计
2. 搜索歌手 - 在已有数据中搜索歌手
3. 爬取指定歌手 - 爬取特定歌手的所有歌曲
4. 下载歌曲 - 下载已爬取的歌曲文件
5. 批量爬取 - 批量处理多个歌手
6. 安全模式 - 使用保守策略爬取
7. 系统设置 - 管理代理和临时文件

💡 使用建议:
- 首次使用建议先用安全模式测试
- 遇到网络问题可尝试使用代理
- 大量爬取时建议分批进行
- 定期清理临时文件节省空间

⚠️  注意事项:
- 请合理控制爬取频率
- 尊重网站服务条款
- 仅供学习研究使用
"""
        print(help_text)
    
    def run(self):
        """运行交互式界面"""
        while True:
            self.clear_screen()
            self.print_header()
            self.show_system_status()
            self.print_menu()
            
            choice = self.get_user_choice("请选择操作", 
                                        ['1', '2', '3', '4', '5', '6', '7', '8'])
            
            try:
                if choice == '1':
                    self.show_system_status()
                elif choice == '2':
                    matches = self.search_singers()
                    if matches:
                        self.display_singers(matches)
                elif choice == '3':
                    self.crawl_specific_singer()
                elif choice == '4':
                    self.download_from_file()
                elif choice == '5':
                    self.batch_crawl_singers()
                elif choice == '6':
                    self.system_settings()
                elif choice == '7':
                    self.show_help()
                elif choice == '8':
                    print("\n👋 感谢使用，再见!")
                    break
                
                if choice != '9':
                    input("\n按回车键继续...")
                    
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，退出系统")
                break
            except Exception as e:
                print(f"\n❌ 操作出错: {e}")
                input("按回车键继续...")

def main():
    """主函数"""
    try:
        app = InteractiveCrawler()
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 再见!")
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")

if __name__ == "__main__":
    main()

