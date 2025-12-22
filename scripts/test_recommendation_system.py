#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试和验证推荐系统功能
检查数据库状态、测试推荐算法、验证API接口
"""

import sys
import os
import sqlite3
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 初始化应用环境
from cps import create_app
app = create_app()

from cps import db, calibre_db, logger, config, ub
from cps.recommendation import get_recommendation_engine

log = logger.create()


def check_database_status():
    """检查数据库状态"""
    print("=" * 60)
    print("1. 检查数据库状态")
    print("=" * 60)
    
    # 检查 metadata.db
    if config.config_calibre_dir:
        metadata_db = os.path.join(config.config_calibre_dir, "metadata.db")
        if os.path.exists(metadata_db):
            print(f"✓ metadata.db 路径: {metadata_db}")
            
            # 统计书籍数量
            conn = sqlite3.connect(metadata_db)
            cur = conn.cursor()
            
            book_count = cur.execute("SELECT COUNT(*) FROM books").fetchone()[0]
            print(f"✓ 图书总数: {book_count}")
            
            tag_count = cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
            print(f"✓ 标签总数: {tag_count}")
            
            author_count = cur.execute("SELECT COUNT(*) FROM authors").fetchone()[0]
            print(f"✓ 作者总数: {author_count}")
            
            comment_count = cur.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
            print(f"✓ 有简介的图书: {comment_count}")
            
            conn.close()
            
            if book_count == 0:
                print("\n警告: 数据库中没有图书!")
                print("请先添加图书到 Calibre 数据库，然后重试。")
                return False
            
            return True
        else:
            print(f"✗ metadata.db 不存在: {metadata_db}")
            return False
    else:
        print("✗ Calibre 数据库路径未配置")
        return False


def check_user_data():
    """检查用户行为数据"""
    print("\n" + "=" * 60)
    print("2. 检查用户行为数据")
    print("=" * 60)
    
    with app.app_context():
        # 检查用户数量
        user_count = ub.session.query(ub.User).filter(ub.User.id > 0).count()
        print(f"✓ 用户总数: {user_count}")
        
        # 检查阅读历史
        read_count = ub.session.query(ub.ReadBook).count()
        print(f"✓ 阅读记录总数: {read_count}")
        
        # 检查收藏（书架）
        shelf_count = ub.session.query(ub.Shelf).count()
        print(f"✓ 书架总数: {shelf_count}")
        
        # 检查推荐缓存
        user_rec_count = ub.session.query(ub.UserRecommendation).count()
        print(f"✓ 用户推荐缓存: {user_rec_count}")
        
        book_rec_count = ub.session.query(ub.BookRecommendation).count()
        print(f"✓ 书籍推荐缓存: {book_rec_count}")
        
        return True


def test_content_recommendation():
    """测试基于内容的推荐"""
    print("\n" + "=" * 60)
    print("3. 测试基于内容的推荐")
    print("=" * 60)
    
    with app.app_context():
        Session = calibre_db.connect()
        if Session is None:
            print("✗ 无法连接到数据库")
            return False
        
        session = Session()
        
        # 获取第一本书
        first_book = session.query(db.Books).first()
        if not first_book:
            print("✗ 数据库中没有书籍")
            return False
        
        print(f"测试书籍: {first_book.title} (ID: {first_book.id})")
        
        # 获取推荐引擎
        engine = get_recommendation_engine(session)
        
        # 生成推荐
        recommendations = engine.get_similar_books(first_book.id, limit=5)
        
        if recommendations:
            print(f"\n找到 {len(recommendations)} 本相似书籍:")
            for idx, (book, score, reason) in enumerate(recommendations, 1):
                print(f"{idx}. {book.title}")
                print(f"   相似度分数: {score:.3f}")
                print(f"   推荐理由: {reason}")
        else:
            print("未找到相似书籍（可能书籍太少或没有共同特征）")
        
        return True


def test_collaborative_filtering():
    """测试协同过滤推荐"""
    print("\n" + "=" * 60)
    print("4. 测试协同过滤推荐")
    print("=" * 60)
    
    with app.app_context():
        # 检查是否有用户阅读历史
        read_books = ub.session.query(ub.ReadBook).limit(5).all()
        
        if not read_books:
            print("警告: 没有用户阅读历史数据")
            print("协同过滤需要用户阅读历史才能工作")
            print("\n建议:")
            print("1. 登录 Calibre-Web")
            print("2. 标记几本书为'已读'")
            print("3. 重新运行此测试")
            return False
        
        print(f"找到 {len(read_books)} 条阅读记录")
        
        # 获取第一个有阅读历史的用户
        user_id = read_books[0].user_id
        user = ub.session.query(ub.User).filter(ub.User.id == user_id).first()
        print(f"测试用户: {user.name} (ID: {user_id})")
        
        Session = calibre_db.connect()
        if Session is None:
            print("✗ 无法连接到数据库")
            return False
        
        session = Session()
        engine = get_recommendation_engine(session)
        
        # 生成推荐
        recommendations = engine.get_user_recommendations(user_id, limit=5)
        
        if recommendations:
            print(f"\n为用户生成 {len(recommendations)} 本推荐书籍:")
            for idx, (book, score, reason) in enumerate(recommendations, 1):
                print(f"{idx}. {book.title}")
                print(f"   推荐分数: {score:.3f}")
                print(f"   推荐理由: {reason}")
        else:
            print("未能生成推荐（可能用户数据不足）")
        
        return True


def main():
    """主函数"""
    print("=" * 60)
    print("Calibre-Web 推荐系统测试工具")
    print("=" * 60)
    
    # 步骤 1: 检查数据库
    if not check_database_status():
        print("\n数据库检查失败，无法继续")
        return
    
    # 步骤 2: 检查用户数据
    check_user_data()
    
    # 步骤 3: 测试基于内容的推荐
    test_content_recommendation()
    
    # 步骤 4: 测试协同过滤
    test_collaborative_filtering()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n如果所有测试都通过，推荐系统已准备就绪！")
    print("\n下一步:")
    print("1. 访问 Calibre-Web (http://localhost:8083)")
    print("2. 登录后查看首页的个性化推荐")
    print("3. 点击任意书籍查看相似书籍推荐")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
    except Exception as e:
        log.error(f"测试过程中出错: {e}")
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

