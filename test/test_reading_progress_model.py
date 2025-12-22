import sys
import os
import pytest

# 1️⃣ 加入项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# 2️⃣ 导入 create_app（只创建一次）
from cps.main import create_app
from cps import ub
from cps.ub import ReadingProgress


@pytest.fixture(scope="session")
def app():
    """
    整个测试会话只创建一次 Flask app
    （避免后台线程重复启动）
    """
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="session")
def app_context(app):
    """
    全局应用上下文
    """
    with app.app_context():
        yield


@pytest.fixture(scope="function")
def session(app_context):
    """
    每个测试使用同一个数据库连接，但事务回滚
    """
    session = ub.session
    session.rollback()
    yield session
    session.rollback()


def test_save_new_progress(session):
    """
    RP-01：保存新的阅读进度
    """
    progress = ReadingProgress(
        user_id=1,
        book_id=1,
        format="epub",
        progress="epubcfi(/6/2)",
        progress_percent=10.0
    )

    session.add(progress)
    session.commit()

    result = session.query(ReadingProgress).filter_by(
        user_id=1, book_id=1, format="epub"
    ).first()

    assert result is not None
    assert result.progress == "epubcfi(/6/2)"


def test_update_progress(session):
    """
    RP-02：更新阅读进度
    """
    progress = session.query(ReadingProgress).filter_by(
        user_id=1, book_id=1, format="epub"
    ).first()

    progress.progress = "epubcfi(/6/10)"
    session.commit()

    updated = session.query(ReadingProgress).filter_by(
        user_id=1, book_id=1, format="epub"
    ).first()

    assert updated.progress == "epubcfi(/6/10)"


def test_get_existing_progress(session):
    """
    RP-03：查询已存在进度
    """
    progress = session.query(ReadingProgress).filter_by(
        user_id=1, book_id=1
    ).first()

    assert progress is not None


def test_get_empty_progress(session):
    """
    RP-04：查询不存在的进度
    """
    progress = session.query(ReadingProgress).filter_by(
        user_id=999, book_id=999
    ).first()

    assert progress is None
