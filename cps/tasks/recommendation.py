# -*- coding: utf-8 -*-
"""
推荐系统定时任务
每日凌晨自动更新推荐结果
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import and_

from ..services.worker import CalibreTask
from .. import logger, db, ub, calibre_db
from ..recommendation import get_recommendation_engine

log = logger.create()


class TaskUpdateRecommendations(CalibreTask):
    """更新推荐结果任务"""

    def __init__(self, message=""):
        super().__init__(message)
        self.log = logger.create()

    def run(self, worker_thread):
        """执行推荐更新任务"""
        try:
            self.log.info("Starting recommendation update task...")
            self.message = "Updating recommendations"
            self.progress = 0
            
            engine = get_recommendation_engine(calibre_db.session)
            
            # 更新所有用户的个性化推荐
            all_users = ub.session.query(ub.User).filter(ub.User.id > 0).all()
            total_users = len(all_users)
            updated_count = 0
            
            for idx, user in enumerate(all_users):
                try:
                    # 获取用户偏好设置
                    user_pref = ub.session.query(ub.UserRecommendationPreference).filter(
                        ub.UserRecommendationPreference.user_id == user.id
                    ).first()
                    preference = user_pref.preference if user_pref else 'balanced'
                    
                    # 生成推荐
                    recommendations = engine.get_user_recommendations(
                        user.id, limit=10, preference=preference
                    )
                    
                    if recommendations:
                        # 删除旧缓存
                        ub.session.query(ub.UserRecommendation).filter(
                            ub.UserRecommendation.user_id == user.id
                        ).delete()
                        
                        # 保存新推荐
                        for book, score, reason in recommendations:
                            user_rec = ub.UserRecommendation(
                                user_id=user.id,
                                book_id=book.id,
                                recommendation_score=score,
                                recommendation_reason=reason
                            )
                            ub.session.add(user_rec)
                        
                        updated_count += 1
                    
                    # 更新进度
                    self.progress = (idx + 1) / total_users * 0.8  # 80% 用于用户推荐
                    
                except Exception as e:
                    log.error(f"Error updating recommendations for user {user.id}: {e}")
                    continue
            
            # 更新所有书籍的相似书籍推荐
            all_books = calibre_db.session.query(db.Books).all()
            total_books = len(all_books)
            book_updated_count = 0
            
            for idx, book in enumerate(all_books):
                try:
                    # 生成相似书籍推荐
                    similar_books = engine.get_similar_books(book.id, limit=5)
                    
                    if similar_books:
                        # 删除旧缓存
                        ub.session.query(ub.BookRecommendation).filter(
                            ub.BookRecommendation.book_id == book.id
                        ).delete()
                        
                        # 保存新推荐
                        for sim_book, score, reason in similar_books:
                            book_rec = ub.BookRecommendation(
                                book_id=book.id,
                                recommended_book_id=sim_book.id,
                                similarity_score=score,
                                recommendation_reason=reason,
                                recommendation_type='content'
                            )
                            ub.session.add(book_rec)
                        
                        book_updated_count += 1
                    
                    # 更新进度
                    self.progress = 0.8 + (idx + 1) / total_books * 0.2  # 20% 用于书籍推荐
                    
                except Exception as e:
                    log.error(f"Error updating similar books for book {book.id}: {e}")
                    continue
            
            # 提交所有更改
            ub.session.commit()
            
            self.progress = 1.0
            self.message = f"Updated recommendations for {updated_count} users and {book_updated_count} books"
            self.log.info(f"Recommendation update completed: {updated_count} users, {book_updated_count} books")
            
        except Exception as e:
            self.log.error(f"Error in recommendation update task: {e}")
            self.message = f"Error: {str(e)}"
            ub.session.rollback()

