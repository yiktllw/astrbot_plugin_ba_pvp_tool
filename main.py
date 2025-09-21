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
        
        # 存储每个用户的监控信息
        # 格式: {unified_msg_origin: {server, friend_code, last_ranking, nickname, task}}
        self.user_monitors = {}
        self.data_file = "data/ba_pvp_monitors.json"
        
        # 初始化插件
        asyncio.create_task(self.async_init())

    async def async_init(self):
        """异步初始化方法"""
        try:
            # 确保data目录存在
            os.makedirs("data", exist_ok=True)
            
            # 加载上次保存的监控数据
            await self.load_monitors_data()
            
            # 重新启动之前的监控任务
            for umo in list(self.user_monitors.keys()):
                task = asyncio.create_task(self.monitor_user(umo))
                self.user_monitors[umo]['task'] = task
            
            logger.info("BA PVP Tool: 插件初始化完成")
        except Exception as e:
            logger.error(f"BA PVP Tool 异步初始化失败: {str(e)}")

    async def load_monitors_data(self):
        """加载监控数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 恢复监控任务（但不包括asyncio.Task对象）
                    for umo, monitor_info in data.items():
                        self.user_monitors[umo] = {
                            'server': monitor_info['server'],
                            'friend_code': monitor_info['friend_code'],
                            'last_ranking': monitor_info.get('last_ranking'),
                            'nickname': monitor_info.get('nickname', ''),
                            'task': None  # 任务会在需要时重新创建
                        }
                    logger.info(f"加载了 {len(self.user_monitors)} 个监控配置")
        except Exception as e:
            logger.error(f"加载监控数据失败: {str(e)}")

    async def save_monitors_data(self):
        """保存监控数据"""
        try:
            # 只保存可序列化的数据，不包括asyncio.Task对象
            save_data = {}
            for umo, monitor_info in self.user_monitors.items():
                save_data[umo] = {
                    'server': monitor_info['server'],
                    'friend_code': monitor_info['friend_code'],
                    'last_ranking': monitor_info.get('last_ranking'),
                    'nickname': monitor_info.get('nickname', ''),
                    'last_update': asyncio.get_event_loop().time()
                }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存了 {len(save_data)} 个监控配置")
        except Exception as e:
            logger.error(f"保存监控数据失败: {str(e)}")

    @filter.command("ba监控")
    async def start_monitor(self, event: AstrMessageEvent, server: str = None, friend_code: str = None):
        """启动BA竞技场监控"""
        if not server or not friend_code:
            help_msg = " BA竞技场监控使用说明:\n\n"
            help_msg += "启动监控: /ba监控 [服务器] [好友码]\n"
            help_msg += "取消监控: /ba取消监控\n"
            help_msg += "查看状态: /ba监控状态\n\n"
            help_msg += "支持的服务器:\n"
            help_msg += " TW - 台湾服\n"
            help_msg += " NA - 北美服\n"
            help_msg += " AS - 亚洲服\n"
            help_msg += " KR - 韩国服\n"
            help_msg += " GL - 国际服\n\n"
            help_msg += "示例: /ba监控 TW ABCDEFGH"
            yield event.plain_result(help_msg)
            return
        
        # 验证服务器参数
        valid_servers = ['TW', 'NA', 'AS', 'KR', 'GL']
        if server.upper() not in valid_servers:
            yield event.plain_result(f" 无效的服务器代码: {server}\n支持的服务器: {', '.join(valid_servers)}")
            return
        
        server = server.upper()
        umo = event.unified_msg_origin
        
        # 检查是否已经在监控
        if umo in self.user_monitors:
            old_info = self.user_monitors[umo]
            yield event.plain_result(f" 您已经在监控中\n服务器: {old_info['server']}\n好友码: {old_info['friend_code']}\n请先使用 /ba取消监控 后再设置新的监控")
            return
        
        # 测试API连接
        yield event.plain_result(" 正在验证好友码...")
        
        try:
            data = await self.fetch_arena_data(server, friend_code)
            if not data or 'data' not in data:
                yield event.plain_result(" 无法获取竞技场数据，请检查好友码是否正确")
                return
            
            current_ranking = data['data'].get('arenaRanking')
            nickname = data['data'].get('nickname', '')
            if current_ranking is None:
                yield event.plain_result(" 获取的数据中没有竞技场排名信息")
                return
            
            # 创建监控配置
            self.user_monitors[umo] = {
                'server': server,
                'friend_code': friend_code,
                'last_ranking': current_ranking,
                'nickname': nickname,
                'task': None
            }
            
            # 启动监控任务
            task = asyncio.create_task(self.monitor_user(umo))
            self.user_monitors[umo]['task'] = task
            
            # 保存数据
            await self.save_monitors_data()
            
            success_msg = f" BA竞技场监控已启动！\n"
            success_msg += f"玩家: {nickname}\n"
            success_msg += f"服务器: {server}\n"
            success_msg += f"当前排名: {current_ranking}\n"
            success_msg += f"监控频率: 每5分钟检查一次\n"
            success_msg += f"如有排名变化将在此会话通知您"
            
            yield event.plain_result(success_msg)
            
        except Exception as e:
            yield event.plain_result(f" 启动监控失败: {str(e)}")

    @filter.command("ba取消监控")
    async def stop_monitor(self, event: AstrMessageEvent):
        """取消BA竞技场监控"""
        umo = event.unified_msg_origin
        
        if umo not in self.user_monitors:
            yield event.plain_result("ℹ 您当前没有正在进行的监控")
            return
        
        try:
            # 取消监控任务
            monitor_info = self.user_monitors[umo]
            if monitor_info['task'] and not monitor_info['task'].done():
                monitor_info['task'].cancel()
                try:
                    await monitor_info['task']
                except asyncio.CancelledError:
                    pass
            
            # 移除监控配置
            del self.user_monitors[umo]
            
            # 保存数据
            await self.save_monitors_data()
            
            yield event.plain_result(" BA竞技场监控已取消")
            
        except Exception as e:
            yield event.plain_result(f" 取消监控失败: {str(e)}")

    @filter.command("ba监控状态")
    async def monitor_status(self, event: AstrMessageEvent):
        """查看监控状态"""
        umo = event.unified_msg_origin
        
        if umo not in self.user_monitors:
            yield event.plain_result("ℹ 您当前没有正在进行的监控")
            return
        
        monitor_info = self.user_monitors[umo]
        is_running = monitor_info['task'] and not monitor_info['task'].done()
        
        status_msg = f" BA竞技场监控状态:\n"
        status_msg += f"玩家: {monitor_info.get('nickname', '未知')}\n"
        status_msg += f"服务器: {monitor_info['server']}\n"
        status_msg += f"好友码: {monitor_info['friend_code']}\n"
        status_msg += f"上次排名: {monitor_info['last_ranking'] if monitor_info['last_ranking'] else '暂无'}\n"
        status_msg += f"运行状态: {' 运行中' if is_running else ' 已停止'}\n"
        status_msg += f"总监控数: {len(self.user_monitors)}"
        
        yield event.plain_result(status_msg)

    async def fetch_arena_data(self, server: str, friend_code: str) -> Optional[Dict[str, Any]]:
        """获取竞技场数据"""
        try:
            payload = {
                "server": server,
                "friendCode": friend_code
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
                        return data
                    else:
                        logger.error(f"获取BA竞技场数据失败，状态码: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"获取BA竞技场数据异常: {str(e)}")
            return None

    async def monitor_user(self, umo: str):
        """监控单个用户的竞技场排名"""
        logger.info(f"开始监控用户 {umo}")
        
        while umo in self.user_monitors:
            try:
                monitor_info = self.user_monitors[umo]
                server = monitor_info['server']
                friend_code = monitor_info['friend_code']
                last_ranking = monitor_info['last_ranking']
                
                # 获取当前数据
                current_data = await self.fetch_arena_data(server, friend_code)
                if not current_data or 'data' not in current_data:
                    logger.warning(f"用户 {umo} 获取竞技场数据失败")
                    await asyncio.sleep(300)  # 5分钟后重试
                    continue
                
                current_ranking = current_data['data'].get('arenaRanking')
                current_nickname = current_data['data'].get('nickname', '')
                if current_ranking is None:
                    logger.warning(f"用户 {umo} 获取的数据中没有arenaRanking字段")
                    await asyncio.sleep(300)
                    continue
                
                # 检查排名变化
                if last_ranking is not None and current_ranking != last_ranking:
                    # 发送变化通知，传递用户名和用户消息源
                    await self.send_ranking_change_notification(umo, last_ranking, current_ranking, server, current_nickname)
                
                # 更新排名和用户名
                self.user_monitors[umo]['last_ranking'] = current_ranking
                self.user_monitors[umo]['nickname'] = current_nickname
                await self.save_monitors_data()
                
                logger.info(f"用户 {umo} 排名检查完成: {current_ranking}")
                
                # 等待5分钟
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                logger.info(f"用户 {umo} 监控任务被取消")
                break
            except Exception as e:
                logger.error(f"用户 {umo} 监控任务执行异常: {str(e)}")
                await asyncio.sleep(60)  # 出错时等待1分钟

    async def send_ranking_change_notification(self, umo: str, old_ranking: int, new_ranking: int, server: str, nickname: str = ''):
        """发送排名变化通知"""
        try:
            # 构建通知消息
            if new_ranking < old_ranking:
                emoji = ""
                change_text = "上升"
            else:
                emoji = ""
                change_text = "下降"
            
            # 从unified_msg_origin解析用户信息来进行@操作
            user_id = None
            if ':' in umo:
                parts = umo.split(':')
                if len(parts) >= 3:
                    user_id = parts[-1]  # 通常用户ID在最后一部分
            
            # 发送消息到原会话
            from astrbot.api.event import MessageChain
            import astrbot.api.message_components as Comp
            
            message_chain = MessageChain()
            
            # 如果有用户ID，先@用户
            if user_id:
                message_chain.chain.append(Comp.At(user_id))
                message_chain.chain.append(Comp.Plain(" "))
            
            # 构建通知内容
            message = f"{emoji} BA竞技场排名变化通知\n"
            if nickname:
                message += f"玩家: {nickname}\n"
            message += f"服务器: {server}\n"
            message += f"排名{change_text}: {old_ranking} -> {new_ranking}\n"
            
            message_chain.chain.append(Comp.Plain(message))
            
            success = await self.context.send_message(umo, message_chain)
            if success:
                logger.info(f"成功发送排名变化通知到 {umo}")
            else:
                logger.error(f"发送排名变化通知失败: {umo}")
                
        except Exception as e:
            logger.error(f"发送排名变化通知时发生异常: {str(e)}")

    async def terminate(self):
        """插件销毁方法"""
        try:
            # 取消所有监控任务
            for umo, monitor_info in self.user_monitors.items():
                if monitor_info['task'] and not monitor_info['task'].done():
                    monitor_info['task'].cancel()
                    try:
                        await monitor_info['task']
                    except asyncio.CancelledError:
                        pass
            
            # 保存数据
            await self.save_monitors_data()
            
            logger.info("BA PVP Tool: 插件已停止，所有监控任务已取消")
        except Exception as e:
            logger.error(f"插件销毁时发生异常: {str(e)}")
