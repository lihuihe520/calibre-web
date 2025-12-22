#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试脚本：检查推荐系统在网页上的集成状态
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 初始化应用环境
from cps import create_app
app = create_app()

from cps import db, ub, calibre_db, config
from cps.recommendation import get_recommendation_engine
from sqlalchemy import func
from sqlalchemy import inspect

def check_recommendation_system():
    """检查推荐系统的各个组件"""
    print("=" * 60)
    print("推荐系统网页集成状态检查")
    print("=" * 60)
    
    with app.app_context():
        # 确保数据库连接已初始化
        try:
            if not hasattr(calibre_db, 'session') or calibre_db.session is None:
                calibre_db.connect()
        except:
            pass
        
        try:
            if not hasattr(ub, 'session') or ub.session is None:
                ub.connect()
        except:
            pass
        # 1. 检查数据库表
        print("\n[1] 检查数据库表...")
        try:
            from cps.ub import add_missing_tables
            # 获取engine
            engine = ub.session.bind if ub.session else None
            if engine:
                add_missing_tables(engine, ub.session)  # 确保表存在
                
                inspector = inspect(engine)
                tables = ['user_recommendation_preference', 'user_recommendation', 'book_recommendation']
                for table in tables:
                    if inspector.has_table(table):
                        print(f"  ✓ {table} 表存在")
                    else:
                        print(f"  ✗ {table} 表不存在")
            else:
                print(f"  ✗ 无法获取数据库引擎")
        except Exception as e:
            print(f"  ✗ 检查表时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 2. 检查书籍数据
        print("\n[2] 检查书籍数据...")
        try:
            book_count = calibre_db.session.query(func.count(db.Books.id)).scalar()
            print(f"  书籍总数: {book_count}")
            
            if book_count == 0:
                print("  ⚠ 警告: 没有书籍数据，推荐系统无法工作")
            else:
                # 检查书籍特征
                sample_book = calibre_db.session.query(db.Books).first()
                if sample_book:
                    authors_count = len(sample_book.authors) if sample_book.authors else 0
                    tags_count = len(sample_book.tags) if sample_book.tags else 0
                    print(f"  示例书籍: {sample_book.title}")
                    print(f"    - 作者数: {authors_count}")
                    print(f"    - 标签数: {tags_count}")
        except Exception as e:
            print(f"  ✗ 检查书籍数据时出错: {e}")
        
        # 3. 检查用户数据
        print("\n[3] 检查用户数据...")
        try:
            user_count = ub.session.query(func.count(ub.User.id)).scalar()
            print(f"  用户总数: {user_count}")
            
            if user_count > 0:
                # 检查用户阅读历史
                read_count = ub.session.query(func.count(ub.ReadBook.id)).scalar()
                print(f"  阅读记录总数: {read_count}")
                
                # 检查用户偏好设置
                pref_count = ub.session.query(func.count(ub.UserRecommendationPreference.id)).scalar()
                print(f"  用户偏好设置数: {pref_count}")
        except Exception as e:
            print(f"  ✗ 检查用户数据时出错: {e}")
        
        # 4. 检查推荐缓存
        print("\n[4] 检查推荐缓存...")
        try:
            user_rec_count = ub.session.query(func.count(ub.UserRecommendation.id)).scalar()
            book_rec_count = ub.session.query(func.count(ub.BookRecommendation.id)).scalar()
            print(f"  用户推荐缓存数: {user_rec_count}")
            print(f"  书籍推荐缓存数: {book_rec_count}")
        except Exception as e:
            print(f"  ✗ 检查推荐缓存时出错: {e}")
        
        # 5. 测试推荐引擎
        print("\n[5] 测试推荐引擎...")
        try:
            engine = get_recommendation_engine(calibre_db.session)
            print("  ✓ 推荐引擎初始化成功")
            
            # 测试获取相似书籍
            sample_book = calibre_db.session.query(db.Books).first()
            if sample_book:
                similar = engine.get_similar_books(sample_book.id, limit=3)
                print(f"  测试相似书籍推荐: 找到 {len(similar)} 本")
                for book, score, reason in similar[:3]:
                    print(f"    - {book.title[:30]:30s} (相似度: {score:.3f})")
        except Exception as e:
            print(f"  ✗ 测试推荐引擎时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 6. 检查网页模板
        print("\n[6] 检查网页模板...")
        # 脚本位置: calibre-web/scripts/debug_web_recommendation.py
        # 模板位置: calibre-web/cps/templates/index.html
        script_file = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_file)  # .../calibre-web/scripts
        calibre_web_dir = os.path.dirname(script_dir)  # .../calibre-web
        template_files = [
            ('cps/templates/index.html', 'recommended_books'),
            ('cps/templates/detail.html', 'similar_books')
        ]
        for template_file, keyword in template_files:
            full_path = os.path.join(calibre_web_dir, template_file)
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if keyword in content:
                        print(f"  ✓ {template_file} 包含推荐相关代码")
                    else:
                        print(f"  ✗ {template_file} 缺少推荐相关代码")
            else:
                print(f"  ✗ {template_file} 文件不存在")
                print(f"    查找路径: {full_path}")
        
        # 7. 检查CSS样式
        print("\n[7] 检查CSS样式...")
        css_file = os.path.join(calibre_web_dir, 'cps/static/css/style.css')
        if os.path.exists(css_file):
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'recommended-books' in content or 'similar-books' in content:
                    print(f"  ✓ CSS文件包含推荐样式")
                else:
                    print(f"  ⚠ CSS文件缺少推荐样式")
        else:
            print(f"  ✗ CSS文件不存在")
            print(f"    查找路径: {css_file}")
        
        # 8. 总结
        print("\n" + "=" * 60)
        print("检查完成！")
        print("=" * 60)
        print("\n建议:")
        print("1. 确保有书籍数据（至少10本以上）")
        print("2. 确保有用户登录并有一些阅读历史")
        print("3. 访问首页查看推荐结果")
        print("4. 访问书籍详情页查看相似书籍推荐")
        print("5. 检查浏览器控制台是否有JavaScript错误")

if __name__ == '__main__':
    check_recommendation_system()

