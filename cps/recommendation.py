# -*- coding: utf-8 -*-
"""
书籍推荐系统模块
实现基于内容推荐和协同过滤的混合推荐算法
"""

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from . import db, ub, logger

log = logger.create()


class BookRecommendationEngine:
    """书籍推荐引擎"""
    
    def __init__(self, session: Session):
        self.session = session
        self.content_weight = 0.6  # 基于内容推荐权重
        self.collaborative_weight = 0.4  # 协同过滤推荐权重
    
    def get_book_features(self, book: db.Books) -> Dict:
        """提取书籍特征向量"""
        features = {
            'authors': [author.id for author in book.authors],
            'tags': [tag.id for tag in book.tags],
            'series': [s.id for s in book.series] if book.series else [],
            'publishers': [p.id for p in book.publishers] if book.publishers else [],
            'languages': [l.id for l in book.languages] if book.languages else [],
            'rating': book.ratings[0].rating if book.ratings else 0,
        }
        return features
    
    def cosine_similarity(self, vec1: Dict, vec2: Dict) -> float:
        """计算两个书籍特征向量的余弦相似度"""
        # 合并所有特征
        all_keys = set(vec1.keys()) | set(vec2.keys())
        
        dot_product = 0
        norm1 = 0
        norm2 = 0
        
        for key in all_keys:
            val1 = vec1.get(key, 0)
            val2 = vec2.get(key, 0)
            
            if isinstance(val1, list):
                # 对于列表类型（authors, tags等），计算交集大小
                set1 = set(val1)
                set2 = set(val2) if isinstance(val2, list) else set()
                val1 = len(set1 & set2)
                val2 = len(set1 | set2) if len(set1 | set2) > 0 else 1
            else:
                # 对于数值类型（rating），直接使用
                val2 = vec2.get(key, 0) if not isinstance(val2, list) else 0
            
            dot_product += val1 * val2
            norm1 += val1 * val1
            norm2 += val2 * val2
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (math.sqrt(norm1) * math.sqrt(norm2))
    
    def content_based_recommend(self, book_id: int, limit: int = 10, 
                                exclude_ids: List[int] = None) -> List[Tuple[db.Books, float, str]]:
        """基于内容的推荐"""
        if exclude_ids is None:
            exclude_ids = []
        
        exclude_ids.append(book_id)
        
        # 获取目标书籍
        target_book = self.session.query(db.Books).filter(db.Books.id == book_id).first()
        if not target_book:
            return []
        
        target_features = self.get_book_features(target_book)
        
        # 获取所有其他书籍
        all_books = self.session.query(db.Books).filter(
            ~db.Books.id.in_(exclude_ids)
        ).all()
        
        similarities = []
        for book in all_books:
            book_features = self.get_book_features(book)
            similarity = self.cosine_similarity(target_features, book_features)
            if similarity > 0:
                similarities.append((book, similarity, "基于内容相似度"))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:limit]
    
    def collaborative_filtering_recommend(self, user_id: int, limit: int = 10,
                                         exclude_ids: List[int] = None) -> List[Tuple[db.Books, float, str]]:
        """协同过滤推荐"""
        if exclude_ids is None:
            exclude_ids = []
        
        # 获取用户的阅读历史
        user_read_books = self.session.query(ub.ReadBook).filter(
            and_(
                ub.ReadBook.user_id == user_id,
                ub.ReadBook.read_status == ub.ReadBook.STATUS_FINISHED
            )
        ).all()
        
        if not user_read_books:
            return []
        
        user_book_ids = [rb.book_id for rb in user_read_books]
        exclude_ids.extend(user_book_ids)
        
        # 找到相似用户（阅读过相同书籍的用户）
        similar_users = self.session.query(ub.ReadBook.user_id).filter(
            and_(
                ub.ReadBook.book_id.in_(user_book_ids),
                ub.ReadBook.user_id != user_id,
                ub.ReadBook.read_status == ub.ReadBook.STATUS_FINISHED
            )
        ).group_by(ub.ReadBook.user_id).having(
            func.count(ub.ReadBook.book_id) >= 2  # 至少阅读过2本相同书籍
        ).all()
        
        if not similar_users:
            return []
        
        similar_user_ids = [u[0] for u in similar_users]
        
        # 获取相似用户阅读但当前用户未读的书籍
        recommended_books = self.session.query(
            ub.ReadBook.book_id,
            func.count(ub.ReadBook.user_id).label('user_count')
        ).filter(
            and_(
                ub.ReadBook.user_id.in_(similar_user_ids),
                ~ub.ReadBook.book_id.in_(exclude_ids),
                ub.ReadBook.read_status == ub.ReadBook.STATUS_FINISHED
            )
        ).group_by(ub.ReadBook.book_id).order_by(
            func.count(ub.ReadBook.user_id).desc()
        ).limit(limit * 2).all()
        
        # 计算推荐分数（基于相似用户数量）
        recommendations = []
        max_count = max([r.user_count for r in recommended_books]) if recommended_books else 1
        
        for book_id, user_count in recommended_books:
            book = self.session.query(db.Books).filter(db.Books.id == book_id).first()
            if book:
                score = user_count / max_count  # 归一化分数
                recommendations.append((book, score, "基于相似用户的阅读历史"))
        
        return recommendations[:limit]
    
    def hybrid_recommend(self, user_id: Optional[int], book_id: Optional[int] = None,
                        limit: int = 10, preference: str = "balanced") -> List[Tuple[db.Books, float, str]]:
        """混合推荐算法"""
        exclude_ids = []
        
        # 根据偏好调整权重
        if preference == "popular":
            self.content_weight = 0.3
            self.collaborative_weight = 0.7
        elif preference == "niche":
            self.content_weight = 0.8
            self.collaborative_weight = 0.2
        else:  # balanced
            self.content_weight = 0.6
            self.collaborative_weight = 0.4
        
        recommendations = {}
        
        # 基于内容的推荐
        if book_id:
            content_recs = self.content_based_recommend(book_id, limit * 2, exclude_ids)
            for book, score, reason in content_recs:
                book_id_key = book.id
                if book_id_key not in recommendations:
                    recommendations[book_id_key] = {
                        'book': book,
                        'content_score': 0,
                        'collaborative_score': 0,
                        'reason': reason
                    }
                recommendations[book_id_key]['content_score'] = score * self.content_weight
        elif user_id:
            # 如果没有 book_id 但有 user_id，尝试基于用户已读书籍进行内容推荐
            user_read_books = self.session.query(ub.ReadBook.book_id).filter(
                and_(
                    ub.ReadBook.user_id == user_id,
                    ub.ReadBook.read_status == ub.ReadBook.STATUS_FINISHED
                )
            ).limit(5).all()
            
            if user_read_books:
                # 基于用户已读书籍进行内容推荐
                for (read_book_id,) in user_read_books:
                    content_recs = self.content_based_recommend(read_book_id, limit, exclude_ids)
                    for book, score, reason in content_recs:
                        book_id_key = book.id
                        if book_id_key not in recommendations:
                            recommendations[book_id_key] = {
                                'book': book,
                                'content_score': 0,
                                'collaborative_score': 0,
                                'reason': reason
                            }
                        recommendations[book_id_key]['content_score'] = max(
                            recommendations[book_id_key]['content_score'],
                            score * self.content_weight
                        )
            else:
                # 用户没有阅读历史，基于所有书籍的热门度推荐
                all_books = self.session.query(db.Books).limit(50).all()
                if all_books:
                    import random
                    # 随机选择几本书作为起点进行内容推荐
                    seed_books = random.sample(all_books, min(3, len(all_books)))
                    for seed_book in seed_books:
                        content_recs = self.content_based_recommend(seed_book.id, limit // len(seed_books) + 1, exclude_ids)
                        for book, score, reason in content_recs:
                            book_id_key = book.id
                            if book_id_key not in recommendations:
                                recommendations[book_id_key] = {
                                    'book': book,
                                    'content_score': 0,
                                    'collaborative_score': 0,
                                    'reason': "基于内容相似度推荐"
                                }
                            recommendations[book_id_key]['content_score'] = max(
                                recommendations[book_id_key]['content_score'],
                                score * self.content_weight * 0.5  # 降低权重，因为是随机推荐
                            )
        
        # 协同过滤推荐
        if user_id:
            collab_recs = self.collaborative_filtering_recommend(user_id, limit * 2, exclude_ids)
            for book, score, reason in collab_recs:
                book_id_key = book.id
                if book_id_key not in recommendations:
                    recommendations[book_id_key] = {
                        'book': book,
                        'content_score': 0,
                        'collaborative_score': 0,
                        'reason': reason
                    }
                recommendations[book_id_key]['collaborative_score'] = score * self.collaborative_weight
                if not recommendations[book_id_key].get('reason'):
                    recommendations[book_id_key]['reason'] = reason
        
        # 合并分数并排序
        final_recommendations = []
        for rec_data in recommendations.values():
            total_score = rec_data['content_score'] + rec_data['collaborative_score']
            if total_score > 0:
                # 确定推荐理由
                if rec_data['content_score'] > rec_data['collaborative_score']:
                    reason = "基于内容相似度"
                elif rec_data['collaborative_score'] > rec_data['content_score']:
                    reason = "基于相似用户的阅读历史"
                else:
                    reason = "基于内容相似度和用户行为"
                
                final_recommendations.append((rec_data['book'], total_score, reason))
        
        # 按总分排序
        final_recommendations.sort(key=lambda x: x[1], reverse=True)
        
        return final_recommendations[:limit]
    
    def get_user_recommendations(self, user_id: int, limit: int = 10,
                                 preference: str = "balanced") -> List[Tuple[db.Books, float, str]]:
        """获取用户个性化推荐（用于首页）"""
        return self.hybrid_recommend(user_id=user_id, limit=limit, preference=preference)
    
    def get_similar_books(self, book_id: int, limit: int = 5) -> List[Tuple[db.Books, float, str]]:
        """获取相似书籍推荐（用于详情页）"""
        return self.content_based_recommend(book_id, limit=limit)


def get_recommendation_engine(session: Session = None) -> BookRecommendationEngine:
    """获取推荐引擎实例"""
    if session is None:
        from . import calibre_db
        session = calibre_db.session
    return BookRecommendationEngine(session)

