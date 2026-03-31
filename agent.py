import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from langchain_community.tools import TavilySearchResults
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

# ========== 1. 加载环境变量 ==========
load_dotenv()

# ========== 2. 初始化模型 ==========
llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0.7,
    api_key=os.getenv("DEEPSEEK_API_KEY")
)

# ========== 3. 定义基础工具 ==========
@tool
def get_current_time() -> str:
    """返回当前时间，当用户问现在几点了时使用此工具"""
    return f"当前时间是: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

@tool
def calculate(expression: str) -> str:
    """计算数学表达式，当用户需要计算时使用此工具
    
    参数:
        expression: 数学表达式，如 '15 * 37 + 28'
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {e}"

@tool
def search_web(query: str) -> str:
    """执行在线搜索获取最新信息。当用户询问新闻、时事、你不知道的知识时使用此工具。"""
    try:
        tavily = TavilySearchResults(
            api_key=os.getenv("TAVILY_API_KEY"),
            max_results=3
        )
        result = tavily.invoke(query)
        
        # 清洗结果
        if isinstance(result, list):
            cleaned = []
            for item in result[:2]:
                title = item.get('title', '')
                content = item.get('content', '')
                if content:
                    content = ' '.join(content.split())[:200]
                    cleaned.append(f"{title}: {content}")
            return "\n".join(cleaned)
        return str(result)
    except Exception as e:
        return f"搜索失败: {e}"

# ========== 4. 创建专员 Agent ==========
time_agent = create_agent(
    model=llm,
    tools=[get_current_time],
    system_prompt="你是一个时间查询专员。用户问时间相关的问题时，调用 get_current_time 工具回答。"
)

calc_agent = create_agent(
    model=llm,
    tools=[calculate],
    system_prompt="你是一个数学计算专员。用户需要计算时，调用 calculate 工具回答。"
)

search_agent = create_agent(
    model=llm,
    tools=[search_web],
    system_prompt="你是一个信息搜索专员。用户需要查询新闻、资讯、实时信息时，调用 search_web 工具回答。"
)

print("✅ 专员 Agent 创建完成")

# ========== 5. 把专员包装成工具（供主管调用） ==========
@tool
def call_time_agent(query: str) -> str:
    """调用时间专员处理时间相关问题。当用户问时间、日期时使用此工具。
    
    参数:
        query: 时间相关的子问题，如'现在几点了'、'今天几号'
    """
    result = time_agent.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content

@tool
def call_calc_agent(query: str) -> str:
    """调用计算专员处理数学计算。当用户需要计算时使用此工具。
    
    参数:
        query: 计算相关的子问题，如'15*37+28'
    """
    result = calc_agent.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content

@tool
def call_search_agent(query: str) -> str:
    """调用搜索专员处理信息查询。当用户需要新闻、实时信息时使用此工具。
    
    参数:
        query: 搜索相关的子问题，如'今天的AI新闻'
    """
    result = search_agent.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content

# 主管可用的工具集
supervisor_tools = [call_time_agent, call_calc_agent, call_search_agent]

# ========== 6. 创建主管 Agent（带记忆） ==========
memory = MemorySaver()

supervisor = create_agent(
    model=llm,
    tools=supervisor_tools,
    system_prompt="""你是一个任务分配主管。根据用户问题，判断需要调用哪个专员工具：

可用的工具：
- call_time_agent：处理时间查询、日期相关问题
- call_calc_agent：处理数学计算、表达式
- call_search_agent：处理信息搜索、新闻、实时信息

规则：
1. 如果用户问题包含多个任务，可以按顺序调用多个工具
2. 每次调用工具时，传入该任务对应的子问题
3. 如果用户不需要工具（如打招呼、闲聊），直接回答
4. 调用完工具后，将结果整合成自然、连贯的回答

示例：
用户："现在几点了？顺便查一下今天的AI新闻"
你应该：
1. 调用 call_time_agent("现在几点了")
2. 调用 call_search_agent("今天的AI新闻")
3. 整合回答："现在是下午3:30。今天的AI新闻有：OpenAI发布新模型..."

记住：你是一个主管，负责分配任务和整合结果，不是具体执行者。
""",
    checkpointer=memory  
)

print("✅ 主管 Agent 创建完成（带记忆功能）")

# ========== 7. 调用函数 ==========
def chat(query: str, session_id: str = "default") -> str:
    """带记忆的多轮对话
    
    Args:
        query: 用户问题
        session_id: 会话ID，相同ID会共享记忆
    
    Returns:
        Agent 回答
    """
    config = {"configurable": {"thread_id": session_id}}
    
    result = supervisor.invoke(
        {"messages": [HumanMessage(content=query)]},
        config=config
    )
    
    return result["messages"][-1].content

def chat_with_print(query: str, session_id: str = "default") -> str:
    """带打印的对话函数（用于测试）"""
    print(f"\n{'='*60}")
    print(f"用户: {query}")
    print(f"{'='*60}")
    
    answer = chat(query, session_id)
    
    print(f"\n🤖 助手: {answer}")
    return answer

# ========== 8. 测试 ==========
if __name__ == "__main__":
    # 测试单任务
    print("=== 测试单任务 ===")
    print(chat("现在几点了？", "test1"))
    
    print("\n=== 测试混合任务 ===")
    print(chat("现在几点了？顺便查一下今天的AI新闻", "test2"))
    
    print("\n=== 测试记忆 ===")
    chat_with_print("我叫小明", "user_123")
    chat_with_print("我叫什么名字？", "user_123")  
    chat_with_print("我叫什么名字？", "user_456")  