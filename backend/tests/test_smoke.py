"""基础工程冒烟测试：应用可创建、路由挂载、OpenAPI 可生成（不依赖外部服务）。"""


def test_app_created():
    from app.main import create_app

    app = create_app()
    assert app.title == "云枢智学"


def test_openapi_generated():
    from app.main import create_app

    schema = create_app().openapi()
    assert "paths" in schema


def test_permission_tree_33_items():
    from app.core.rbac import PERMISSION_CODES, PERMISSION_TREE

    assert len(PERMISSION_TREE) == 9
    assert len(PERMISSION_CODES) == 33
