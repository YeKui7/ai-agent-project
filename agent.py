from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from langchain_community.tools import TavilySearchResults
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import os
from datetime import datetime
import re

load_dotenv()

# ========== 1. 初始化模型 ==========
llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0.7,
    api_key=os.getenv("DEEPSEEK_API_KEY")
)

# ========== 2. 定义基础工具 ==========
@tool
def get_current_time() -> str:
    """返回当前时间"""
    return f"当前时间是: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

@tool
def calculate(expression: str) -> str:
    """计算数学表达式"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {e}"

@tool
def search_web(query: str) -> str:
    """执行在线搜索获取最新信息"""
    try:
        tavily = TavilySearchResults(
            api_key=os.getenv("TAVILY_API_KEY"),
            max_results=2
        )
        result = tavily.invoke(query)
        if isinstance(result, list):
            cleaned = []
            for item in result:
                title = item.get('title', '')
                content = item.get('content', '')
                if content:
                    content = ' '.join(content.split())[:150]
                    cleaned.append(f"{title}: {content}")
            return "\n".join(cleaned)
        return str(result)
    except Exception as e:
        return f"搜索失败: {e}"

# ========== 3. 创建专员Agent ==========
time_agent = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt="你是一个时间查询专员。用户问时间时，调用get_current_time。"
)

calc_agent = create_agent(
    model=llm,
    tools=[calculate],
    system_prompt="你是一个计算专员。用户需要计算时，调用calculate。"
)

search_agent = create_agent(
    model=llm,
    tools=[search_web],
    system_prompt="你是一个搜索专员。用户需要查询信息时，调用search_web。"
)

# ========== 4. 升级版主管：处理混合问题 ==========
def supervisor_v2(query: str) -> str:
    """主管：识别混合问题，分步处理"""
    
    # 第一步：分析问题中包含哪些任务
    analysis_prompt = f"""
分析用户问题中包含哪些类型的需求，用逗号分隔返回：

问题：{query}

可选类型：
- time：时间查询（几点了、日期等）
- calc：数学计算（加减乘除、计算等）
- search：信息搜索（新闻、查询、找资料等）

示例1："现在几点了？帮我查新闻" → time,search
示例2："计算15*37，顺便问时间" → calc,time
示例3："今天有什么新闻" → search
示例4："你好" → none

只返回类型，不要其他文字：
"""
    
    task_types = llm.invoke(analysis_prompt).content.strip().lower()
    print(f"📋 识别到任务: {task_types}")
    
    # 第二步：如果没有任务，直接回答
    if task_types == "none" or not task_types:
        return llm.invoke(query).content
    
    # 第三步：拆分任务并执行
    tasks = [t.strip() for t in task_types.split(',')]
    results = {}
    
    # 定义任务执行函数
    def execute_task(task_type, original_query):
        """根据任务类型执行，提取相关部分"""
        
        # 提取该任务相关的子问题
        extract_prompt = f"""
从原问题中提取出{task_type}相关的部分：
原问题：{original_query}

如果是time：只保留时间相关的部分
如果是calc：只保留计算相关的部分
如果是search：只保留搜索相关的部分

直接返回提取后的子问题：
"""
        sub_query = llm.invoke(extract_prompt).content.strip()
        
        # 交给对应专员
        if task_type == "time":
            result = time_agent.invoke({"messages": [HumanMessage(content=sub_query)]})
            return result["messages"][-1].content
        elif task_type == "calc":
            result = calc_agent.invoke({"messages": [HumanMessage(content=sub_query)]})
            return result["messages"][-1].content
        elif task_type == "search":
            result = search_agent.invoke({"messages": [HumanMessage(content=sub_query)]})
            return result["messages"][-1].content
        return ""
    
    # 执行所有任务
    for task in tasks:
        print(f"🔧 正在执行: {task}")
        results[task] = execute_task(task, query)
    
    # 第四步：汇总结果
    summary_prompt = f"""
用户原问题：{query}

各任务执行结果：
{chr(10).join([f'- {k}: {v}' for k, v in results.items()])}

请将这些结果整合成一个完整、自然的回答：
"""
    
    final_answer = llm.invoke(summary_prompt).content
    return final_answer

# ========== 5. 测试混合问题 ==========
def test_mixed_queries():
    test_cases = [
        "现在几点了？顺便帮我查一下今天的AI新闻",
        "计算 15*37+28，然后告诉我现在的时间",
        "帮我搜索最近的科技新闻，再算一下 2的10次方",
        "现在几点了？帮我查新闻，顺便算一下 123+456"
    ]
    
    for query in test_cases:
        print(f"\n{'='*60}")
        print(f"用户: {query}")
        print(f"{'='*60}")
        
        answer = supervisor_v2(query)
        print(f"助手: {answer}")

test_mixed_queries()