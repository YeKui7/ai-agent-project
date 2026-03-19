# 在项目目录运行这个检查
import os
from pathlib import Path

print("📁 当前目录:", os.getcwd())
print("\n📄 检查 .env 文件状态:")

env_path = Path(".env")
if env_path.exists():
    print(f"✅ .env 文件存在: {env_path.absolute()}")
    
    # 检查是否在 .gitignore 中
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding='utf-8')
        if ".env" in content:
            print("✅ .env 已在 .gitignore 中")
        else:
            print("❌ .env 未在 .gitignore 中，请立即添加！")
    else:
        print("⚠️ 未找到 .gitignore 文件，建议创建")
else:
    print("❌ .env 文件不存在")

# 检查 .env.example
env_example = Path(".env.example")
if env_example.exists():
    print("✅ .env.example 存在")
else:
    print("❌ .env.example 不存在，请创建")