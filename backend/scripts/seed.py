"""种子数据脚本（02 §4.2）：预置 3 角色 + 内置超管 + 系统设置单行。

口径来源：
  - 预置角色与权限（需求 4.5.2）：super_admin=全部权限（免检，不落 role_permission）；
    content_reviewer=只把关不生产（查看全部内容并审核题目，无增删改）；
    operator=除系统管理/用户管理外全部操作，含内容维护与学员管理，无审核权限。
  - 内置超管唯一（03 §2.1.1）：username=admin（app.common.constants），
    初始/默认密码=应用层常量 ADMIN_DEFAULT_PASSWORD（上线前应强制修改）。
幂等：已存在同 code 角色/同 username 账号则跳过。

运行：cd backend && .venv/Scripts/python.exe scripts/seed.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.common import constants as C  # noqa: E402
from app.core import security  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.rbac import (  # noqa: E402
    ROLE_CONTENT_REVIEWER,
    ROLE_OPERATOR,
    ROLE_SUPER_ADMIN,
)
from app.modules.system.models import AdminUser, Role, RolePermission, SystemSetting  # noqa: E402

# 预置角色权限（需求 4.5.2；super_admin 免检不落行）
PRESET_ROLE_PERMS: dict[str, tuple[str, list[str]]] = {
    ROLE_SUPER_ADMIN: ("超级管理员", []),  # 全部权限（免检）
    ROLE_CONTENT_REVIEWER: (
        "内容审核",
        [
            "subject:view", "course:view", "question:view", "question:review",
            "interviewbank:view", "route:view",
        ],
    ),
    ROLE_OPERATOR: (
        "运营人员",
        [
            "dashboard:view",
            "subject:view", "subject:create", "subject:edit", "subject:delete",
            "course:view", "course:create", "course:edit", "course:delete",
            "question:view", "question:create", "question:edit", "question:delete",
            "question:import", "question:export",
            "interviewbank:view", "interviewbank:edit", "interviewbank:delete",
            "route:view", "route:create", "route:edit", "route:delete",
            "student:view", "student:edit", "student:delete",
        ],
    ),
}


async def main() -> None:
    async with SessionLocal() as db:
        # 1) 预置角色 + 权限点
        for code, (name, perms) in PRESET_ROLE_PERMS.items():
            role = (
                await db.execute(select(Role).where(Role.code == code, Role.deleted_at.is_(None)))
            ).scalar_one_or_none()
            if role is None:
                role = Role(code=code, name=name, description=f"预置角色：{name}", is_preset=1)
                db.add(role)
                await db.flush()
                for perm in perms:
                    db.add(RolePermission(role_id=role.id, permission_code=perm))
                print(f"[seed] 角色 {code} 已创建（{len(perms)} 个权限点）")
            else:
                print(f"[seed] 角色 {code} 已存在，跳过")

        # 2) 内置超管（唯一）
        admin = (
            await db.execute(
                select(AdminUser).where(
                    AdminUser.username == C.ADMIN_SUPER_USERNAME,
                    AdminUser.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if admin is None:
            super_role = (
                await db.execute(
                    select(Role).where(Role.code == ROLE_SUPER_ADMIN, Role.deleted_at.is_(None))
                )
            ).scalar_one()
            db.add(
                AdminUser(
                    username=C.ADMIN_SUPER_USERNAME,
                    password_hash=security.hash_password(C.ADMIN_DEFAULT_PASSWORD),
                    phone="13800000000",  # 占位手机号（业务唯一），上线前改为真实联系方式
                    role_id=super_role.id,
                    status=1,
                )
            )
            print(f"[seed] 内置超管 {C.ADMIN_SUPER_USERNAME} 已创建")
        else:
            print(f"[seed] 内置超管 {C.ADMIN_SUPER_USERNAME} 已存在，跳过")

        # 3) 系统设置单行（id=1）
        setting = (
            await db.execute(select(SystemSetting).where(SystemSetting.id == 1))
        ).scalar_one_or_none()
        if setting is None:
            db.add(SystemSetting(id=1, platform_name="云枢智学", good_rate=98.00))
            print("[seed] system_setting 单行已创建")

        await db.commit()
        print("[seed] 完成")


if __name__ == "__main__":
    asyncio.run(main())
