"""蓝图集合模块。

汇总全部功能蓝图，供应用工厂统一注册，
避免在 create_app 中出现大量散乱的 import。
"""

from .enrollment import bp as enrollment_bp
from .main import bp as main_bp
from .stats import bp as stats_bp
from .students import bp as students_bp
from .universities import bp as universities_bp

#: 注册到应用的全部蓝图（顺序即注册顺序）
ALL_BLUEPRINTS = (
    main_bp,
    students_bp,
    universities_bp,
    enrollment_bp,
    stats_bp,
)
