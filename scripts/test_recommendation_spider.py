#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的书籍爬虫脚本，用于测试推荐系统
从公开API或网站爬取书籍信息并添加到Calibre数据库
"""

import sys
import os
import requests
import json
from datetime import datetime, timezone

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 初始化应用环境
from cps import create_app
app = create_app()

from cps import db, calibre_db, logger, config, cli_param

log = logger.create()


def fetch_books_from_openlibrary(query="python programming", limit=10):
    """
    从 Open Library API 获取书籍信息
    """
    books_data = []
    try:
        url = "https://openlibrary.org/search.json"
        params = {
            "q": query,
            "limit": limit,
            "fields": "title,author_name,subject,isbn,first_publish_year,language"
        }
        
        print(f"  正在请求API: {url}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        docs = data.get("docs", [])
        print(f"  API返回了 {len(docs)} 条结果")
        
        for doc in docs[:limit]:
            # 确保有标题和作者
            title = doc.get("title", "Unknown")
            author_name = doc.get("author_name", [])
            
            if not title or title == "Unknown":
                print(f"  跳过无效书籍（无标题）")
                continue
            
            if not author_name:
                author_name = ["Unknown Author"]
            
            book_info = {
                "title": title,
                "authors": author_name if isinstance(author_name, list) else [author_name],
                "subjects": doc.get("subject", [])[:5] if doc.get("subject") else [],
                "isbn": doc.get("isbn", [None])[0] if doc.get("isbn") else None,
                "pubdate": datetime(doc.get("first_publish_year", 2000), 1, 1, tzinfo=timezone.utc) if doc.get("first_publish_year") else datetime(2000, 1, 1, tzinfo=timezone.utc),
                "language": doc.get("language", ["eng"])[0] if doc.get("language") else "eng"
            }
            books_data.append(book_info)
            print(f"  解析书籍: {book_info['title']} by {', '.join(book_info['authors'])}")
            
    except Exception as e:
        log.error(f"Error fetching books from Open Library: {e}")
        print(f"  错误: {e}")
        import traceback
        traceback.print_exc()
    
    return books_data


def add_book_to_calibre(book_info, session):
    """
    将书籍信息添加到Calibre数据库
    注意：这个函数只添加元数据，不添加实际文件
    """
    try:
        # 检查书籍是否已存在（通过标题和作者）
        existing_book = session.query(db.Books).filter(
            db.Books.title == book_info["title"]
        ).first()
        
        if existing_book:
            print(f"    书籍已存在: {book_info['title']}")
            log.info(f"Book '{book_info['title']}' already exists, skipping...")
            return None
        
        # 创建或获取作者
        authors = []
        for author_name in book_info["authors"]:
            author = session.query(db.Authors).filter(
                db.Authors.name == author_name
            ).first()
            if not author:
                author = db.Authors(name=author_name, sort=author_name)
                session.add(author)
                session.flush()
            authors.append(author)
        
        # 创建或获取标签
        tags = []
        for tag_name in book_info.get("subjects", [])[:5]:
            tag = session.query(db.Tags).filter(
                db.Tags.name == tag_name
            ).first()
            if not tag:
                tag = db.Tags(name=tag_name)
                session.add(tag)
                session.flush()
            tags.append(tag)
        
        # 创建书籍 - 按照 Books.__init__ 的参数顺序
        # 注意：__init__ 中的 has_cover 逻辑是 (has_cover is not None)，
        # 所以传入 None 会设置为 0，传入任何非 None 值会设置为 1
        # authors 和 tags 参数在 __init__ 中不会被设置，需要在创建后通过关系属性设置
        new_book = db.Books(
            book_info["title"],  # title
            book_info["title"],  # sort
            ", ".join(book_info["authors"]),  # author_sort
            datetime.now(timezone.utc),  # timestamp
            book_info["pubdate"],  # pubdate
            "1.0",  # series_index
            datetime.now(timezone.utc),  # last_modified
            f"test/{book_info['title'].replace(' ', '_')}",  # path
            None,  # has_cover (传入 None 会设置为 0，传入非 None 会设置为 1)
            authors[0] if authors else None,  # authors (传入第一个作者或 None，但之后会通过关系设置)
            tags if tags else [],  # tags (传入标签列表，但之后会通过关系设置)
            None  # languages (可选)
        )
        
        # 设置 authors 和 tags 关系（因为 __init__ 不会自动设置这些关系）
        new_book.authors = authors
        new_book.tags = tags
        
        # 设置 ISBN（通过属性赋值，因为 isbn 是列但不是 __init__ 参数）
        if book_info.get("isbn"):
            new_book.isbn = book_info["isbn"]
        
        session.add(new_book)
        session.flush()  # 先 flush 以获取 book.id
        session.commit()
        
        print(f"    ✓ 成功添加: {book_info['title']}")
        log.info(f"Added book: {book_info['title']} by {', '.join(book_info['authors'])}")
        return new_book
        
    except Exception as e:
        print(f"    ✗ 添加失败: {book_info['title']} - {e}")
        log.error(f"Error adding book '{book_info['title']}': {e}")
        import traceback
        traceback.print_exc()
        if session:
            try:
        session.rollback()
            except:
                pass
        return None


def find_metadata_db():
    """
    自动查找 metadata.db 文件
    """
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(script_dir, "library", "metadata.db"),  # library/metadata.db
        os.path.join(script_dir, "metadata.db"),  # 当前目录的 metadata.db
    ]
    
    for db_path in possible_paths:
        if os.path.exists(db_path):
            db_dir = os.path.dirname(db_path)
            print(f"  找到数据库: {db_path}")
            return db_dir
    
        return None


def main():
    """
    主函数：爬取书籍并添加到数据库
    """
    print("=" * 60)
    print("书籍推荐系统测试爬虫")
    print("=" * 60)
    
    # 确保在 app context 中
    with app.app_context():
        # 检查并设置数据库路径
        if not config.config_calibre_dir or not os.path.exists(os.path.join(config.config_calibre_dir, "metadata.db")):
            print("\n检测到数据库路径未配置或无效，正在自动查找...")
            db_dir = find_metadata_db()
            if db_dir:
                print(f"  设置数据库路径为: {db_dir}")
                config.config_calibre_dir = db_dir
                config.save()
                # 更新 calibre_db 配置
                db.CalibreDB.update_config(config, config.config_calibre_dir, cli_param.settings_path)
            else:
                print("错误: 无法找到 metadata.db 文件。")
                print("请确保以下位置之一存在 metadata.db:")
                print("  1. library/metadata.db")
                print("  2. metadata.db (当前目录)")
                print("\n或者通过 Web 界面配置数据库路径:")
                print("  访问 http://localhost:8083/admin/config 设置 Calibre 数据库路径")
                return
        
        # 初始化数据库会话 - 直接使用 connect() 方法
        Session = calibre_db.connect()
        if Session is None:
            print("\n错误: 无法连接到数据库。请确保:")
            print("1. Calibre 数据库路径已正确配置")
            print("2. metadata.db 文件存在且可访问")
            print(f"   当前配置路径: {config.config_calibre_dir}")
            if config.config_calibre_dir:
                db_path = os.path.join(config.config_calibre_dir, "metadata.db")
                print(f"   数据库文件路径: {db_path}")
                print(f"   文件是否存在: {os.path.exists(db_path)}")
            return
        
        # scoped_session 需要调用才能获取实际的 session
        session = Session()
    
    # 定义要爬取的主题
    queries = [
        "python programming",
        "machine learning",
        "web development",
        "data science",
        "javascript",
        "java programming",
        "database design",
        "software engineering"
    ]
    
    total_added = 0
    
    for query in queries:
        print(f"\n正在爬取主题: {query}")
        books_data = fetch_books_from_openlibrary(query, limit=5)
        print(f"  获取到 {len(books_data)} 本有效书籍")
        
        added_count = 0
        for book_info in books_data:
            book = add_book_to_calibre(book_info, session)
            if book:
                total_added += 1
                added_count += 1
        
        print(f"  本次添加了 {added_count} 本书籍")
    
    print(f"\n总共添加了 {total_added} 本书籍到数据库")
    print("\n爬取完成！现在可以测试推荐系统了。")
    print("\n提示：")
    print("1. 登录系统后，在首页查看个性化推荐")
    print("2. 点击任意书籍，查看相似书籍推荐")
    print("3. 在用户设置中调整推荐偏好")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
    except Exception as e:
        log.error(f"Error in main: {e}")
        print(f"\n发生错误: {e}")

