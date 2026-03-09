"""
LLM Agent - 剪映智能辅助大脑
使用多模态大模型（GLM-4V / GPT-4o）进行 UI 理解和操作规划
支持智谱 AI GLM 和 OpenAI API（兼容格式）
"""
import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from zhipuai import ZhipuAI


class JianyingAgent:
    """剪映辅助 Agent - 基于视觉大模型的动态探索型智能体"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化 Agent
        
        Args:
            api_key: API Key（支持 OpenAI、GLM 等兼容 API）
            base_url: API 基础 URL
        """
        self.api_key = api_key or os.getenv("GLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("❌ 未设置 API Key，请在 .env 中配置 GLM_API_KEY")
        
        # 初始化智谱 AI 客户端（官方 SDK）
        # 设置较长的超时时间（120秒），因为图像分析需要更长时间
        self.client = ZhipuAI(
            api_key=self.api_key,
            timeout=120.0  # 120秒超时
        )
        
        # 加载 UI 拓扑地图
        self.schema = self._load_schema()
        
        # 默认模型（GLM-4-Flash 支持视觉理解，速度更快）
        self.model = os.getenv("LLM_MODEL", "glm-4-flash")
        
        print(f"✅ LLM Agent 初始化成功（智谱 AI 官方 SDK）")
        print(f"   模型: {self.model}")
    
    def _load_schema(self) -> Dict[str, Any]:
        """加载 UI 拓扑地图配置"""
        schema_path = Path(__file__).parent / "schema.json"
        
        if not schema_path.exists():
            raise FileNotFoundError(f"❌ 未找到 schema.json: {schema_path}")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        
        print(f"✅ 已加载 UI 拓扑地图: {schema.get('description', 'N/A')}")
        return schema
    
    def _build_system_prompt(self, user_goal: str) -> str:
        """
        构建 System Prompt
        
        Args:
            user_goal: 用户的目标描述（如"加一个老电视特效"）
        
        Returns:
            完整的 System Prompt
        """
        schema_str = json.dumps(self.schema, ensure_ascii=False, indent=2)
        
        prompt = f"""你是一个专业的剪映（Jianying）桌面端辅助 Agent。你的任务是帮助用户完成视频剪辑操作。

**用户当前目标**：{user_goal}

**系统 UI 拓扑地图**：
```json
{schema_str}
```

**🔴 核心工作流程（必须严格遵守）**：

**第一步：判断当前界面状态**
- 仔细观察截图，识别当前在哪个界面/面板
- 判断已经完成了哪些步骤
- 常见状态：
  * 主编辑页（看到时间轴、预览窗口）
  * 特效面板（顶部【特效】按钮高亮，中间显示特效列表）
  * 音频面板（顶部【音频】按钮高亮）
  * 文本面板（顶部【文本】按钮高亮）

**第二步：决定下一步操作**
- 如果已经在目标面板（如特效面板），**不要**再次点击顶部菜单
- 如果搜索框可见且未输入，应该输入搜索关键词
- 如果已显示搜索结果，应该选择特效并拖拽或点击应用

**第三步：输出操作指令**
- 识别截图中的目标 UI 元素（按钮、搜索框、特效项等）
- 给出精确的坐标和清晰的提示

**输出格式**（必须返回纯 JSON，不要任何解释）：
```json
{{
  "action": "click|input_text|wait|complete",
  "box": [x, y, width, height],
  "tooltip": "第一步：点击特效菜单",
  "reason": "当前界面停留在主编辑页，需要先切换到特效面板",
  "params": {{}}
}}
```

**支持的操作类型（action）**：

1. **click** - 鼠标点击操作（默认）
   示例：{{"action": "click", "box": [124,42,146,69], "tooltip": "点击特效菜单"}}

2. **input_text** - 在输入框输入文字
   示例：{{"action": "input_text", "box": [96,91,368,111], "tooltip": "输入'老电视'", "params": {{"text": "老电视"}}}}
   - params.text: 要输入的文字内容（必填）

3. **wait** - 等待界面加载或动画完成
   示例：{{"action": "wait", "box": null, "tooltip": "等待搜索结果加载...", "params": {{"duration": 1500}}}}
   - params.duration: 等待时间（毫秒）

4. **complete** - 任务完成，停止自动化流程
   示例：{{"action": "complete", "box": null, "tooltip": "✅ 已成功添加老电视特效"}}

**🔴 关于特效/滤镜/贴纸的应用方式（极其重要，tooltip 必须说清楚）**：

剪映中"点击特效缩略图"仅触发预览，并**不会**自动添加到视频。用户需要知道具体的应用方法：

方法A（最常见）：**拖拽法**
- 鼠标按住特效缩略图不放 → 拖拽到下方时间轴的视频轨道上方 → 松开鼠标
- 时间轴上方会出现一条紫色/蓝色特效轨道，即代表成功

方法B（部分版本）：**双击法**
- 双击特效缩略图，弹出预览窗口 → 再点击【添加到轨道】/【应用】/【确定】按钮

**当前步骤是"选择特效"时，tooltip 模板（必须照此写）**：
"用鼠标【按住不放】此特效缩略图，拖拽到下方时间轴的视频轨道上方后松开，即可添加特效。时间轴上出现新的特效轨道后点击【已完成】按钮结束引导。"

**重要规则**：
- **🔴 最重要：先看当前截图在哪个界面，不要盲目从第一步开始！**
- **🔴 观察截图变化判断成功：如果上一步的操作已生效（界面发生变化），不要重复相同操作**
- 如果截图显示已经在特效面板（顶部特效按钮高亮），直接进行下一步操作，不要再点击特效按钮
- 如果截图显示搜索框已有内容，不要重复输入
- 如果截图显示特效列表已加载，直接选择特效
- `action` 必须是上述4种类型之一
- `box` 坐标是相对于截图左上角的像素：[x坐标, y坐标, 宽度, 高度]，wait/complete 操作可以为 null
- **🔴 tooltip 必须极其详细说明完整操作，包括点击后要做什么**
  * ❌ 错误："点击特效" → 用户完全不知道点击后该干什么
  * ❌ 错误："点击这个按钮" → 用户不知道点击后要观察什么或继续做什么
  * ✅ 正确："点击此特效预览效果 → 然后拖拽到下方时间轴，或点击弹出的【应用】/【确定】按钮"
  * ✅ 正确："点击【添加素材】按钮 → 等待弹窗加载 → 在弹窗中选择文件 → 点击【确定】"
  * ✅ 正确："点击搜索框后输入'老电视'关键词 → 等待搜索结果加载"
  * ✅ 正确："将此特效用鼠标拖拽到下方时间轴视频轨道上 → 松开鼠标完成添加"
- **🔴 reason 必须包含两部分**：
  1. 当前状态判断（例如："观察到顶部特效按钮高亮且面板已打开，搜索框可见"）
  2. **上一步结果验证**（例如："上一步点击后，界面成功切换，时间轴出现新特效轨道" 或 "上一步搜索后，列表显示3个相关特效"）
- **🔴 极其重要：观察界面变化判断成功**
  * 如果时间轴出现新轨道/新素材（轨道数量增加、出现有颜色的色块） → 操作成功，**立即**输出 complete
  * 如果搜索结果已显示（列表中有缩略图） → 不要重复搜索，直接指向第一个缩略图并说明拖拽方法
  * 如果面板已打开（按钮高亮） → 不要重复点击打开按钮
  * 如果弹窗已出现 → 不要重复点击触发弹窗的按钮
  * 如果截图中时间轴区域和上次完全一致（无新轨道） → 说明用户还没有成功拖拽，再次给出拖拽指引，不要切换步骤
- **🔴 "下一步"按钮用途说明**：用户每次操作后会点击"下一步"按钮触发新截图，系统会根据新截图判断操作结果。用户还有一个"已完成"按钮可以自行终止引导。
- `params` 某些操作需要额外参数，没有参数时可以为空对象 {{}}
- **直接输出 JSON，不要思考过程，不要解释，不要markdown代码块**

**🔴 完整操作流程说明（tooltip 必须详细）**：
1. 点击按钮打开面板：tooltip 应说明 "点击以打开XX面板"
2. 输入搜索关键词：tooltip 应说明 "输入'关键词'搜索特效"
3. 选择特效：tooltip 应说明 "点击此特效预览 → 拖拽到时间轴或点击【应用】按钮"
4. 确认应用：tooltip 应说明 "点击【确定】/【应用】按钮完成添加"
5. 观察结果：在 reason 中说明 "时间轴上已出现特效图层" 或 "预览窗口显示特效已生效"

**状态判断示例**：
- 如果看到顶部"特效"按钮被高亮/选中 → 已在特效面板，不要再点击特效菜单
- 如果看到搜索框（通常在顶部或左上） → 应该输入搜索关键词
- 如果看到特效缩略图列表 → 选择特效，tooltip 说明"拖拽到时间轴或点击应用按钮"
- 如果时间轴上出现新的特效轨道 → 特效已成功添加，输出 complete

**工作流示例**（根据当前状态自适应）：
情况1 - 当前在主页：
```json
{{"action": "click", "box": [124,42,146,69], "tooltip": "点击【特效】按钮打开特效面板", "reason": "当前在主编辑页，顶部菜单栏中特效按钮未高亮，需要切换到特效面板"}}
```

情况2 - 当前已在特效面板，看到搜索框：
```json
{{"action": "input_text", "box": [96,91,368,111], "tooltip": "在搜索框输入'老电视'查找特效", "params": {{"text": "老电视"}}, "reason": "观察到已在特效面板（顶部特效按钮高亮），搜索框可见但为空，直接搜索特效"}}
```

情况3 - 搜索结果已显示，看到特效列表：
```json
{{"action": "click", "box": [特效位置], "tooltip": "点击此特效预览效果 → 然后用鼠标拖拽到下方时间轴的视频轨道上，或等待弹出窗口后点击【应用】/【确定】按钮", "reason": "上一步搜索成功，列表已显示3个老电视特效缩略图，选择第一个最匹配的特效"}}
```

情况4 - 点击后需要拖拽或确认：
```json
{{"action": "click", "box": [应用按钮], "tooltip": "点击【应用】/【添加】/【确定】按钮，将特效添加到时间轴", "reason": "上一步点击了特效进入预览，但时间轴未出现新轨道，需要点击确认按钮完成添加"}}
```

情况5 - 特效已成功添加（时间轴出现新轨道）：
```json
{{"action": "complete", "box": null, "tooltip": "✅ 老电视特效已成功添加到时间轴！", "reason": "上一步操作成功：时间轴底部出现了新的特效轨道/图层，预览窗口也显示特效已生效"}}
```

情况6 - 验证成功的关键指标：
- 时间轴区域出现新的轨道/图层/素材块
- 预览窗口画面发生变化（应用了特效/滤镜）
- 列表中素材数量增加
- 弹窗关闭返回主界面
**如果观察到这些变化，立即输出 complete，不要继续重复操作！**

**🔴 关键：每次都要先在 reason 中说明你观察到的当前状态，然后再给出操作！**

现在，请：
1. 先观察截图，判断当前在哪个界面
2. 在 reason 字段说明你的判断依据
3. 再给出下一步操作
"""
        return prompt
    
    async def analyze_screenshot(
        self, 
        base64_image: str, 
        user_goal: str = "加一个老电视特效"
    ) -> Dict[str, Any]:
        """
        分析截图并返回下一步操作指令
        
        Args:
            base64_image: Base64 编码的截图（PNG/JPEG）
            user_goal: 用户目标描述
        
        Returns:
            操作指令 JSON：{"action": "highlight", "box": [x,y,w,h], "tooltip": "..."}
        """
        try:
            import time
            start_time = time.time()
            
            print(f"\n🧠 LLM Agent 开始分析...")
            print(f"   目标: {user_goal}")
            print(f"   图片大小: {len(base64_image)} 字符 ({len(base64_image) / 1024 / 1024:.2f} MB)")
            
            # 构建 System Prompt
            system_prompt = self._build_system_prompt(user_goal)
            
            # 调用多模态大模型
            print(f"   ⏳ 正在调用 {self.model}...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请直接输出 JSON 格式的操作指令，不要有任何解释或思考过程。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500,  # 增加到 1500，确保有足够空间生成完整答案
                temperature=0.1,  # 降低随机性，提高准确度
                top_p=0.7  # 增加确定性
            )
            
            elapsed_time = time.time() - start_time
            print(f"   ✅ API 响应时间: {elapsed_time:.2f} 秒")
            
            # 打印完整的 API 响应对象（调试用）
            print(f"\n🔍 API 响应详情：")
            print(f"   Response ID: {response.id}")
            print(f"   Model: {response.model}")
            print(f"   Choices 数量: {len(response.choices) if response.choices else 0}")
            
            # 检查 API 响应是否有效
            if not response.choices or len(response.choices) == 0:
                print(f"   ❌ response.choices 为空！完整响应: {response}")
                raise ValueError("API 返回了空的 choices 列表")
            
            choice = response.choices[0]
            print(f"   Finish Reason: {choice.finish_reason}")
            print(f"   Message Role: {choice.message.role}")
            
            # GLM-4.6V 支持思维链，需要检查两个字段
            message = choice.message
            regular_content = message.content
            reasoning_content = getattr(message, 'reasoning_content', None)
            
            print(f"   Regular Content: {repr(regular_content[:100] if regular_content else 'None')}")
            print(f"   Reasoning Content: {repr(reasoning_content[:100] if reasoning_content else 'None')}")
            
            # 优先使用 regular content（正常回复），如果为空才回退到 reasoning_content
            if regular_content and regular_content.strip():
                llm_output = regular_content.strip()
                print(f"   ✅ 使用 regular content")
            elif reasoning_content and reasoning_content.strip():
                llm_output = reasoning_content.strip()
                print(f"   ⚠️ regular content 为空，使用 reasoning_content（思维链回退）")
            else:
                print(f"   ❌ content 和 reasoning_content 都为空！")
                raise ValueError("API 返回的 content 和 reasoning_content 都为空")
            
            # 提取 LLM 返回的文本
            
            print(f"   处理后 llm_output 长度: {len(llm_output)}")
            print(f"   处理后 llm_output (repr): {repr(llm_output[:100])}")
            
            if not llm_output:
                print(f"   ❌ llm_output 为空字符串！")
                raise ValueError("LLM 返回了空字符串")
            
            print(f"\n📤 LLM 原始输出 ({len(llm_output)} 字符)：\n{llm_output}\n")
            
            # 解析 JSON
            # 移除可能的 markdown 代码块标记
            if llm_output.startswith("```json"):
                llm_output = llm_output[7:]
            if llm_output.startswith("```"):
                llm_output = llm_output[3:]
            if llm_output.endswith("```"):
                llm_output = llm_output[:-3]
            llm_output = llm_output.strip()
            
            result = json.loads(llm_output)
            
            # ✅ 直接返回 LLM 的原始输出，保留所有字段
            # 确保必需字段存在
            instruction = {
                "action": result.get("action", "click"),  # 使用 LLM 返回的 action
                "box": result.get("box", [100, 100, 200, 50]),
                "tooltip": result.get("tooltip", "点击这里"),
                "reason": result.get("reason", ""),
                "params": result.get("params", {})  # 保留 params 参数
            }
            
            print(f"✅ LLM 解析成功：")
            print(f"   操作类型: {instruction['action']}")
            print(f"   坐标: {instruction['box']}")
            print(f"   提示: {instruction['tooltip']}")
            print(f"   原因: {instruction['reason']}")
            if instruction['params']:
                print(f"   参数: {instruction['params']}")
            
            return instruction
            
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON 解析失败: {e}")
            print(f"   错误位置: line {e.lineno} column {e.colno}")
            print(f"   错误文档: {repr(e.doc[:200] if e.doc else 'N/A')}")
            # 安全地打印原始输出
            try:
                print(f"   llm_output 变量类型: {type(llm_output)}")
                print(f"   llm_output 长度: {len(llm_output)}")
                print(f"   llm_output 前500字符: {llm_output[:500]}")
                print(f"   llm_output (repr): {repr(llm_output[:200])}")
            except Exception as print_err:
                print(f"   无法打印 llm_output: {print_err}")
            # 返回降级响应
            return {
                "action": "highlight",
                "box": [200, 50, 100, 40],
                "tooltip": "解析失败，请重试",
                "error": str(e)
            }
        
        except ValueError as e:
            # API 返回内容为空的情况
            print(f"\n❌ ValueError: {e}")
            print(f"   提示: 可能是 API 超时、配额用尽、网络问题或内容违规")
            # 尝试打印 response 对象
            try:
                if 'response' in locals():
                    print(f"   Response 对象存在: {response}")
                    print(f"   Response choices: {response.choices if hasattr(response, 'choices') else 'N/A'}")
                else:
                    print(f"   Response 对象不存在（可能 API 调用失败）")
            except Exception as debug_err:
                print(f"   调试信息打印失败: {debug_err}")
            
            return {
                "action": "highlight",
                "box": [200, 50, 100, 40],
                "tooltip": "AI 暂时不可用",
                "error": str(e)
            }
        
        except Exception as e:
            print(f"\n❌ 未预期的异常: {type(e).__name__}: {e}")
            # 打印更详细的错误信息
            import traceback
            print(f"   详细堆栈:\n{traceback.format_exc()}")
            
            # 检查是否是智谱 AI SDK 的特定异常
            exception_type = type(e).__name__
            if "APIError" in exception_type or "RateLimitError" in exception_type or "APIConnectionError" in exception_type:
                print(f"   ⚠️ 这是智谱 AI API 错误，可能原因：")
                print(f"      - API 配额用尽")
                print(f"      - API Key 无效或过期")
                print(f"      - 网络连接问题")
                print(f"      - 请求内容违规")
            
            # 返回降级响应
            return {
                "action": "highlight",
                "box": [200, 50, 100, 40],
                "tooltip": "AI 分析出错，请重试",
                "error": f"{type(e).__name__}: {str(e)}"
            }


# 全局单例
_agent_instance: Optional[JianyingAgent] = None


def get_agent() -> JianyingAgent:
    """获取全局 Agent 实例（单例模式）"""
    global _agent_instance
    
    if _agent_instance is None:
        _agent_instance = JianyingAgent()
    
    return _agent_instance
