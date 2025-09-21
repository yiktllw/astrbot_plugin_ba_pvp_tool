from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import asyncio
import aiohttp
import json
import os
from typing import Dict, Any, Optional

@register("ba_pvp_tool", "yiktllw", "BA竞技场排名监控插件", "1.0.0")
class BA_PVP_Tool(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.context = context
        self.config = config
        self.notice_id = ""
        self.server = "TW"
        self.friend_code = ""
        self.last_arena_ranking = None
        self.monitoring_task = None
        self.data_file = "data/ba_pvp_data.json"
        
        # 初始化插件
        asyncio.create_task(self.async_init())

    async def async_init(self):
        """异步初始化方法"""
        try:
            # 获取配置
            if self.config:
                self.notice_id = self.config.get("notice_id", "").strip()
                self.server = self.config.get("server", "TW").strip()
                self.friend_code = self.config.get("friend_code", "").strip()
            else:
                # 如果config为None，从context获取配置
                config = self.context.get_config()
                self.notice_id = config.get("notice_id", "").strip()
                self.server = config.get("server", "TW").strip()
                self.friend_code = config.get("friend_code", "").strip()
            
            logger.info(f"BA PVP Tool 初始化: notice_id={self.notice_id}, server={self.server}, friend_code={self.friend_code}")
            
            # 检查必要配置是否为空
            if not self.notice_id or not self.friend_code:
                logger.warning("BA PVP Tool: notice_id 或 friend_code 为空，插件不会启动监控功能")
                return
            
            # 确保data目录存在
            os.makedirs("data", exist_ok=True)
            
            # 加载上次保存的数据
            await self.load_last_data()
            
            # 启动监控任务
            self.monitoring_task = asyncio.create_task(self.start_monitoring())
            logger.info("BA PVP Tool: 监控任务已启动")
        except Exception as e:
            logger.error(f"BA PVP Tool 异步初始化失败: {str(e)}")

    async def fetch_arena_data(self) -> Optional[Dict[str, Any]]:
        """获取竞技场数据"""
        try:
            payload = {
                "server": self.server,
                "friendCode": self.friend_code
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://bacrawl.diyigemt.com/api/v1/friendsearch",
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"成功获取BA竞技场数据: {data}")
                        return data
                    else:
                        logger.error(f"获取BA竞技场数据失败，状态码: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"获取BA竞技场数据异常: {str(e)}")
            return None

    async def load_last_data(self):
        """加载上次保存的数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.last_arena_ranking = data.get('last_arena_ranking')
                    logger.info(f"加载上次的竞技场排名: {self.last_arena_ranking}")
        except Exception as e:
            logger.error(f"加载历史数据失败: {str(e)}")

    async def save_data(self, arena_ranking):
        """保存当前数据"""
        try:
            data = {
                'last_arena_ranking': arena_ranking,
                'last_update': asyncio.get_event_loop().time()
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存竞技场排名数据: {arena_ranking}")
        except Exception as e:
            logger.error(f"保存数据失败: {str(e)}")

    async def check_arena_ranking_change(self) -> Optional[Dict[str, Any]]:
        """检查竞技场排名变化"""
        try:
            # 获取当前数据
            current_data = await self.fetch_arena_data()
            if not current_data or 'data' not in current_data:
                logger.warning("获取竞技场数据失败或数据格式错误")
                return None
            
            current_ranking = current_data['data'].get('arenaRanking')
            if current_ranking is None:
                logger.warning("获取的数据中没有arenaRanking字段")
                return None
            
            # 如果是第一次运行，保存当前数据并发送初始化消息
            if self.last_arena_ranking is None:
                self.last_arena_ranking = current_ranking
                await self.save_data(current_ranking)
                logger.info(f"首次运行，保存初始排名: {current_ranking}")
                
                # 发送初始化成功消息
                await self.send_initialization_message(current_ranking, current_data)
                return None
            
            # 检查排名是否发生变化
            if current_ranking != self.last_arena_ranking:
                change_info = {
                    'old_ranking': self.last_arena_ranking,
                    'new_ranking': current_ranking,
                    'change_type': 'up' if current_ranking < self.last_arena_ranking else 'down',
                    'full_data': current_data
                }
                
                # 更新保存的排名
                self.last_arena_ranking = current_ranking
                await self.save_data(current_ranking)
                
                logger.info(f"检测到排名变化: {change_info['old_ranking']} -> {change_info['new_ranking']}")
                return change_info
            
            logger.info(f"排名无变化: {current_ranking}")
            return None
            
        except Exception as e:
            logger.error(f"检查排名变化时发生异常: {str(e)}")
            return None

    async def send_initialization_message(self, ranking: int, full_data: Dict[str, Any]):
        """发送插件初始化成功消息"""
        try:
            # 构建初始化消息
            message = f"🎮 BA竞技场监控插件启动成功！\n"
            message += f"服务器: {self.server}\n"
            message += f"当前排名: {ranking}\n"
            message += f"监控频率: 每5分钟检查一次\n"
            message += f"如有排名变化将及时通知您"
            
            # 构建会话标识 - 使用aiocqhttp平台的私聊格式
            unified_msg_origin = f"aiocqhttp:private:{self.notice_id}"
            
            # 发送消息
            from astrbot.api.event import MessageChain
            import astrbot.api.message_components as Comp
            
            message_chain = MessageChain()
            message_chain.chain = [Comp.Plain(message)]
            
            success = await self.context.send_message(unified_msg_origin, message_chain)
            if success:
                logger.info(f"成功发送初始化消息到 {self.notice_id}")
            else:
                logger.error(f"发送初始化消息失败，可能找不到对应的消息平台")
                
        except Exception as e:
            logger.error(f"发送初始化消息时发生异常: {str(e)}")

    async def send_notification(self, change_info: Dict[str, Any]):
        """发送排名变化通知"""
        try:
            old_ranking = change_info['old_ranking']
            new_ranking = change_info['new_ranking']
            change_type = change_info['change_type']
            
            # 构建通知消息
            if change_type == 'up':
                emoji = "📈"
                change_text = "上升"
            else:
                emoji = "📉"
                change_text = "下降"
            
            message = f"{emoji} BA竞技场排名变化通知\n"
            message += f"服务器: {self.server}\n"
            message += f"排名{change_text}: {old_ranking} → {new_ranking}\n"
            message += f"变化: {abs(new_ranking - old_ranking)} 位"
            
            # 构建会话标识
            # 使用aiocqhttp平台的私聊格式
            unified_msg_origin = f"aiocqhttp:private:{self.notice_id}"
            
            # 发送消息
            from astrbot.api.event import MessageChain
            import astrbot.api.message_components as Comp
            
            message_chain = MessageChain()
            message_chain.chain = [Comp.Plain(message)]
            
            success = await self.context.send_message(unified_msg_origin, message_chain)
            if success:
                logger.info(f"成功发送通知到 {self.notice_id}")
            else:
                logger.error(f"发送通知失败，可能找不到对应的消息平台")
                
        except Exception as e:
            logger.error(f"发送通知时发生异常: {str(e)}")

    async def start_monitoring(self):
        """启动监控任务"""
        logger.info("开始BA竞技场排名监控，每5分钟检查一次")
        
        while True:
            try:
                # 检查排名变化
                change_info = await self.check_arena_ranking_change()
                
                if change_info:
                    # 发送通知
                    await self.send_notification(change_info)
                
                # 等待5分钟
                await asyncio.sleep(300)  # 5分钟 = 300秒
                
            except asyncio.CancelledError:
                logger.info("监控任务被取消")
                break
            except Exception as e:
                logger.error(f"监控任务执行时发生异常: {str(e)}")
                # 发生异常时等待1分钟后重试
                await asyncio.sleep(60)

    @filter.command("ba_pvp_status")
    async def check_status(self, event: AstrMessageEvent):
        """检查BA PVP监控状态"""
        if not self.notice_id or not self.friend_code:
            yield event.plain_result("BA PVP Tool: 配置不完整，notice_id 或 friend_code 为空")
            return
        
        if self.monitoring_task and not self.monitoring_task.done():
            status = "监控运行中"
        else:
            status = "监控已停止"
        
        msg = f"BA PVP Tool 状态:\n"
        msg += f"监控状态: {status}\n"
        msg += f"服务器: {self.server}\n"
        msg += f"好友码: {self.friend_code}\n"
        msg += f"通知QQ: {self.notice_id}\n"
        msg += f"上次排名: {self.last_arena_ranking if self.last_arena_ranking else '暂无数据'}"
        
        yield event.plain_result(msg)

    @filter.command("ba_pvp_test")
    async def test_check(self, event: AstrMessageEvent):
        """手动测试竞技场排名检查"""
        if not self.notice_id or not self.friend_code:
            yield event.plain_result("BA PVP Tool: 配置不完整，notice_id 或 friend_code 为空")
            return
        
        yield event.plain_result("正在获取竞技场数据...")
        
        try:
            data = await self.fetch_arena_data()
            if data and 'data' in data:
                arena_ranking = data['data'].get('arenaRanking')
                if arena_ranking is not None:
                    msg = f"当前竞技场排名: {arena_ranking}\n"
                    msg += f"上次记录排名: {self.last_arena_ranking if self.last_arena_ranking else '暂无'}\n"
                    
                    if self.last_arena_ranking is not None:
                        if arena_ranking != self.last_arena_ranking:
                            change_type = "上升" if arena_ranking < self.last_arena_ranking else "下降"
                            msg += f"排名{change_type}: {abs(arena_ranking - self.last_arena_ranking)} 位"
                        else:
                            msg += "排名无变化"
                    
                    yield event.plain_result(msg)
                else:
                    yield event.plain_result("获取的数据中没有arenaRanking字段")
            else:
                yield event.plain_result("获取竞技场数据失败")
        except Exception as e:
            yield event.plain_result(f"测试时发生错误: {str(e)}")

    @filter.command("ba_pvp_force_update")
    async def force_update(self, event: AstrMessageEvent):
        """强制更新当前排名数据"""
        if not self.notice_id or not self.friend_code:
            yield event.plain_result("BA PVP Tool: 配置不完整，notice_id 或 friend_code 为空")
            return
        
        try:
            data = await self.fetch_arena_data()
            if data and 'data' in data:
                arena_ranking = data['data'].get('arenaRanking')
                if arena_ranking is not None:
                    old_ranking = self.last_arena_ranking
                    self.last_arena_ranking = arena_ranking
                    await self.save_data(arena_ranking)
                    
                    msg = f"强制更新排名数据成功\n"
                    msg += f"旧排名: {old_ranking if old_ranking else '暂无'}\n"
                    msg += f"新排名: {arena_ranking}"
                    
                    yield event.plain_result(msg)
                else:
                    yield event.plain_result("获取的数据中没有arenaRanking字段")
            else:
                yield event.plain_result("获取竞技场数据失败")
        except Exception as e:
            yield event.plain_result(f"强制更新时发生错误: {str(e)}")

    async def terminate(self):
        """插件销毁方法"""
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("BA PVP Tool: 插件已停止，监控任务已取消")
