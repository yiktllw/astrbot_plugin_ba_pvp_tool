from astrbot.api.event import filter, AstrMessageEvent, MessageEventResultfrom astrbot.api.event import filter, AstrMessageEvent, MessageEventResult

from astrbot.api.star import Context, Star, registerfrom astrbot.api.star import Context, Star, register

from astrbot.api import logger, AstrBotConfigfrom astrbot.api import logger, AstrBotConfig

import asyncioimport asyncio

import aiohttpimport aiohttp

import jsonimport json

import osimport os

from typing import Dict, Any, Optionalfrom typing import Dict, Any, Optional



@register("ba_pvp_tool", "yiktllw", "BA竞技场排名监控插件", "1.0.0")@register("ba_pvp_tool", "yiktllw", "BA竞技场排名监控插件", "1.0.0")

class BA_PVP_Tool(Star):class BA_PVP_Tool(Star):

    def __init__(self, context: Context, config: AstrBotConfig = None):    def __init__(self, context: Context, config: AstrBotConfig = None):

        super().__init__(context)        super().__init__(context)

        self.context = context        self.context = context

        self.config = config        self.config = config

                

        # 存储每个用户的监控信息        # 存储每个用户的监控信息

        # 格式: {unified_msg_origin: {server, friend_code, last_ranking, task}}        # 格式: {unified_msg_origin: {server, friend_code, last_ranking, task}}

        self.user_monitors = {}        self.user_monitors = {}

        self.data_file = "data/ba_pvp_monitors.json"        self.data_file = "data/ba_pvp_monitors.json"

                

        # 初始化插件        # 初始化插件

        asyncio.create_task(self.async_init())        asyncio.create_task(self.async_init())



    async def async_init(self):    async def async_init(self):

        """异步初始化方法"""        """异步初始化方法"""

        try:        try:

            # 确保data目录存在            # 确保data目录存在

            os.makedirs("data", exist_ok=True)            os.makedirs("data", exist_ok=True)

                        

            # 加载上次保存的监控数据            # 加载上次保存的监控数据

            await self.load_monitors_data()            await self.load_monitors_data()

                        

            # 重新启动之前的监控任务            logger.info("BA PVP Tool: 插件初始化完成")

            for umo in list(self.user_monitors.keys()):        except Exception as e:

                task = asyncio.create_task(self.monitor_user(umo))            logger.error(f"BA PVP Tool 异步初始化失败: {str(e)}")

                self.user_monitors[umo]['task'] = task

                async def load_monitors_data(self):

            logger.info("BA PVP Tool: 插件初始化完成")        """加载监控数据"""

        except Exception as e:        try:

            logger.error(f"BA PVP Tool 异步初始化失败: {str(e)}")            if os.path.exists(self.data_file):

                with open(self.data_file, 'r', encoding='utf-8') as f:

    async def load_monitors_data(self):                    data = json.load(f)

        """加载监控数据"""                    # 恢复监控任务（但不包括asyncio.Task对象）

        try:                    for umo, monitor_info in data.items():

            if os.path.exists(self.data_file):                        self.user_monitors[umo] = {

                with open(self.data_file, 'r', encoding='utf-8') as f:                            'server': monitor_info['server'],

                    data = json.load(f)                            'friend_code': monitor_info['friend_code'],

                    # 恢复监控任务（但不包括asyncio.Task对象）                            'last_ranking': monitor_info.get('last_ranking'),

                    for umo, monitor_info in data.items():                            'task': None  # 任务会在需要时重新创建

                        self.user_monitors[umo] = {                        }

                            'server': monitor_info['server'],                    logger.info(f"加载了 {len(self.user_monitors)} 个监控配置")

                            'friend_code': monitor_info['friend_code'],        except Exception as e:

                            'last_ranking': monitor_info.get('last_ranking'),            logger.error(f"加载监控数据失败: {str(e)}")

                            'task': None  # 任务会在需要时重新创建

                        }    async def save_monitors_data(self):

                    logger.info(f"加载了 {len(self.user_monitors)} 个监控配置")        """保存监控数据"""

        except Exception as e:        try:

            logger.error(f"加载监控数据失败: {str(e)}")            # 只保存可序列化的数据，不包括asyncio.Task对象

            save_data = {}

    async def save_monitors_data(self):            for umo, monitor_info in self.user_monitors.items():

        """保存监控数据"""                save_data[umo] = {

        try:                    'server': monitor_info['server'],

            # 只保存可序列化的数据，不包括asyncio.Task对象                    'friend_code': monitor_info['friend_code'],

            save_data = {}                    'last_ranking': monitor_info.get('last_ranking'),

            for umo, monitor_info in self.user_monitors.items():                    'last_update': asyncio.get_event_loop().time()

                save_data[umo] = {                }

                    'server': monitor_info['server'],            

                    'friend_code': monitor_info['friend_code'],            with open(self.data_file, 'w', encoding='utf-8') as f:

                    'last_ranking': monitor_info.get('last_ranking'),                json.dump(save_data, f, ensure_ascii=False, indent=2)

                    'last_update': asyncio.get_event_loop().time()            logger.info(f"保存了 {len(save_data)} 个监控配置")

                }        except Exception as e:

                        logger.error(f"保存监控数据失败: {str(e)}")

            with open(self.data_file, 'w', encoding='utf-8') as f:

                json.dump(save_data, f, ensure_ascii=False, indent=2)    @filter.command("ba监控")

            logger.info(f"保存了 {len(save_data)} 个监控配置")    async def start_monitor(self, event: AstrMessageEvent, server: str = None, friend_code: str = None):

        except Exception as e:        """启动BA竞技场监控"""

            logger.error(f"保存监控数据失败: {str(e)}")        if not server or not friend_code:

            help_msg = "📖 BA竞技场监控使用说明:\n\n"

    @filter.command("ba监控")            help_msg += "启动监控: /ba监控 [服务器] [好友码]\n"

    async def start_monitor(self, event: AstrMessageEvent, server: str = None, friend_code: str = None):            help_msg += "取消监控: /ba取消监控\n\n"

        """启动BA竞技场监控"""            help_msg += "支持的服务器:\n"

        if not server or not friend_code:            help_msg += "• TW - 台湾服\n"

            help_msg = "📖 BA竞技场监控使用说明:\n\n"            help_msg += "• NA - 北美服\n"

            help_msg += "启动监控: /ba监控 [服务器] [好友码]\n"            help_msg += "• AS - 亚洲服\n"

            help_msg += "取消监控: /ba取消监控\n"            help_msg += "• KR - 韩国服\n"

            help_msg += "查看状态: /ba监控状态\n\n"            help_msg += "• GL - 国际服\n\n"

            help_msg += "支持的服务器:\n"            help_msg += "示例: /ba监控 TW ABCDEFGH"

            help_msg += "• TW - 台湾服\n"            yield event.plain_result(help_msg)

            help_msg += "• NA - 北美服\n"            return

            help_msg += "• AS - 亚洲服\n"        

            help_msg += "• KR - 韩国服\n"        # 验证服务器参数

            help_msg += "• GL - 国际服\n\n"        valid_servers = ['TW', 'NA', 'AS', 'KR', 'GL']

            help_msg += "示例: /ba监控 TW ABCDEFGH"        if server.upper() not in valid_servers:

            yield event.plain_result(help_msg)            yield event.plain_result(f"❌ 无效的服务器代码: {server}\n支持的服务器: {', '.join(valid_servers)}")

            return            return

                

        # 验证服务器参数        server = server.upper()

        valid_servers = ['TW', 'NA', 'AS', 'KR', 'GL']        umo = event.unified_msg_origin

        if server.upper() not in valid_servers:        

            yield event.plain_result(f"❌ 无效的服务器代码: {server}\n支持的服务器: {', '.join(valid_servers)}")        # 检查是否已经在监控

            return        if umo in self.user_monitors:

                    old_info = self.user_monitors[umo]

        server = server.upper()            yield event.plain_result(f"⚠️ 您已经在监控中\n服务器: {old_info['server']}\n好友码: {old_info['friend_code']}\n请先使用 /ba取消监控 后再设置新的监控")

        umo = event.unified_msg_origin            return

                

        # 检查是否已经在监控        # 测试API连接

        if umo in self.user_monitors:        yield event.plain_result("🔍 正在验证好友码...")

            old_info = self.user_monitors[umo]        

            yield event.plain_result(f"⚠️ 您已经在监控中\n服务器: {old_info['server']}\n好友码: {old_info['friend_code']}\n请先使用 /ba取消监控 后再设置新的监控")        try:

            return            data = await self.fetch_arena_data(server, friend_code)

                    if not data or 'data' not in data:

        # 测试API连接                yield event.plain_result("❌ 无法获取竞技场数据，请检查好友码是否正确")

        yield event.plain_result("🔍 正在验证好友码...")                return

                    

        try:            current_ranking = data['data'].get('arenaRanking')

            data = await self.fetch_arena_data(server, friend_code)            if current_ranking is None:

            if not data or 'data' not in data:                yield event.plain_result("❌ 获取的数据中没有竞技场排名信息")

                yield event.plain_result("❌ 无法获取竞技场数据，请检查好友码是否正确")                return

                return            

                        # 创建监控配置

            current_ranking = data['data'].get('arenaRanking')            self.user_monitors[umo] = {

            if current_ranking is None:                'server': server,

                yield event.plain_result("❌ 获取的数据中没有竞技场排名信息")                'friend_code': friend_code,

                return                'last_ranking': current_ranking,

                            'task': None

            # 创建监控配置            }

            self.user_monitors[umo] = {            

                'server': server,            # 启动监控任务

                'friend_code': friend_code,            task = asyncio.create_task(self.monitor_user(umo))

                'last_ranking': current_ranking,            self.user_monitors[umo]['task'] = task

                'task': None            

            }            # 保存数据

                        await self.save_monitors_data()

            # 启动监控任务            

            task = asyncio.create_task(self.monitor_user(umo))            success_msg = f"✅ BA竞技场监控已启动！\n"

            self.user_monitors[umo]['task'] = task            success_msg += f"服务器: {server}\n"

                        success_msg += f"当前排名: {current_ranking}\n"

            # 保存数据            success_msg += f"监控频率: 每5分钟检查一次\n"

            await self.save_monitors_data()            success_msg += f"如有排名变化将在此会话通知您"

                        

            success_msg = f"✅ BA竞技场监控已启动！\n"            yield event.plain_result(success_msg)

            success_msg += f"服务器: {server}\n"            

            success_msg += f"当前排名: {current_ranking}\n"        except Exception as e:

            success_msg += f"监控频率: 每5分钟检查一次\n"            yield event.plain_result(f"❌ 启动监控失败: {str(e)}")

            success_msg += f"如有排名变化将在此会话通知您"

                @filter.command("ba取消监控")

            yield event.plain_result(success_msg)    async def stop_monitor(self, event: AstrMessageEvent):

                    """取消BA竞技场监控"""

        except Exception as e:        umo = event.unified_msg_origin

            yield event.plain_result(f"❌ 启动监控失败: {str(e)}")        

        if umo not in self.user_monitors:

    @filter.command("ba取消监控")            yield event.plain_result("ℹ️ 您当前没有正在进行的监控")

    async def stop_monitor(self, event: AstrMessageEvent):            return

        """取消BA竞技场监控"""        

        umo = event.unified_msg_origin        try:

                    # 取消监控任务

        if umo not in self.user_monitors:            monitor_info = self.user_monitors[umo]

            yield event.plain_result("ℹ️ 您当前没有正在进行的监控")            if monitor_info['task'] and not monitor_info['task'].done():

            return                monitor_info['task'].cancel()

                        try:

        try:                    await monitor_info['task']

            # 取消监控任务                except asyncio.CancelledError:

            monitor_info = self.user_monitors[umo]                    pass

            if monitor_info['task'] and not monitor_info['task'].done():            

                monitor_info['task'].cancel()            # 移除监控配置

                try:            del self.user_monitors[umo]

                    await monitor_info['task']            

                except asyncio.CancelledError:            # 保存数据

                    pass            await self.save_monitors_data()

                        

            # 移除监控配置            yield event.plain_result("✅ BA竞技场监控已取消")

            del self.user_monitors[umo]            

                    except Exception as e:

            # 保存数据            yield event.plain_result(f"❌ 取消监控失败: {str(e)}")

            await self.save_monitors_data()

                @filter.command("ba监控状态")

            yield event.plain_result("✅ BA竞技场监控已取消")    async def monitor_status(self, event: AstrMessageEvent):

                    """查看监控状态"""

        except Exception as e:        umo = event.unified_msg_origin

            yield event.plain_result(f"❌ 取消监控失败: {str(e)}")        

        if umo not in self.user_monitors:

    @filter.command("ba监控状态")            yield event.plain_result("ℹ️ 您当前没有正在进行的监控")

    async def monitor_status(self, event: AstrMessageEvent):            return

        """查看监控状态"""        

        umo = event.unified_msg_origin        monitor_info = self.user_monitors[umo]

                is_running = monitor_info['task'] and not monitor_info['task'].done()

        if umo not in self.user_monitors:        

            yield event.plain_result("ℹ️ 您当前没有正在进行的监控")        status_msg = f"📊 BA竞技场监控状态:\n"

            return        status_msg += f"服务器: {monitor_info['server']}\n"

                status_msg += f"好友码: {monitor_info['friend_code']}\n"

        monitor_info = self.user_monitors[umo]        status_msg += f"上次排名: {monitor_info['last_ranking'] if monitor_info['last_ranking'] else '暂无'}\n"

        is_running = monitor_info['task'] and not monitor_info['task'].done()        status_msg += f"运行状态: {'🟢 运行中' if is_running else '🔴 已停止'}\n"

                status_msg += f"总监控数: {len(self.user_monitors)}"

        status_msg = f"📊 BA竞技场监控状态:\n"        

        status_msg += f"服务器: {monitor_info['server']}\n"    async def fetch_arena_data(self, server: str, friend_code: str) -> Optional[Dict[str, Any]]:

        status_msg += f"好友码: {monitor_info['friend_code']}\n"        """获取竞技场数据"""

        status_msg += f"上次排名: {monitor_info['last_ranking'] if monitor_info['last_ranking'] else '暂无'}\n"        try:

        status_msg += f"运行状态: {'🟢 运行中' if is_running else '🔴 已停止'}\n"            payload = {

        status_msg += f"总监控数: {len(self.user_monitors)}"                "server": server,

                        "friendCode": friend_code

        yield event.plain_result(status_msg)            }

            

    async def fetch_arena_data(self, server: str, friend_code: str) -> Optional[Dict[str, Any]]:            timeout = aiohttp.ClientTimeout(total=30)

        """获取竞技场数据"""            async with aiohttp.ClientSession(timeout=timeout) as session:

        try:                async with session.post(

            payload = {                    "https://bacrawl.diyigemt.com/api/v1/friendsearch",

                "server": server,                    json=payload,

                "friendCode": friend_code                    headers={'Content-Type': 'application/json'}

            }                ) as response:

                                if response.status == 200:

            timeout = aiohttp.ClientTimeout(total=30)                        data = await response.json()

            async with aiohttp.ClientSession(timeout=timeout) as session:                        return data

                async with session.post(                    else:

                    "https://bacrawl.diyigemt.com/api/v1/friendsearch",                        logger.error(f"获取BA竞技场数据失败，状态码: {response.status}")

                    json=payload,                        return None

                    headers={'Content-Type': 'application/json'}        except Exception as e:

                ) as response:            logger.error(f"获取BA竞技场数据异常: {str(e)}")

                    if response.status == 200:            return None

                        data = await response.json()

                        return data    async def monitor_user(self, umo: str):

                    else:        """监控单个用户的竞技场排名"""

                        logger.error(f"获取BA竞技场数据失败，状态码: {response.status}")        logger.info(f"开始监控用户 {umo}")

                        return None        

        except Exception as e:        while umo in self.user_monitors:

            logger.error(f"获取BA竞技场数据异常: {str(e)}")            try:

            return None                monitor_info = self.user_monitors[umo]

                server = monitor_info['server']

    async def monitor_user(self, umo: str):                friend_code = monitor_info['friend_code']

        """监控单个用户的竞技场排名"""                last_ranking = monitor_info['last_ranking']

        logger.info(f"开始监控用户 {umo}")                

                        # 获取当前数据

        while umo in self.user_monitors:                current_data = await self.fetch_arena_data(server, friend_code)

            try:                if not current_data or 'data' not in current_data:

                monitor_info = self.user_monitors[umo]                    logger.warning(f"用户 {umo} 获取竞技场数据失败")

                server = monitor_info['server']                    await asyncio.sleep(300)  # 5分钟后重试

                friend_code = monitor_info['friend_code']                    continue

                last_ranking = monitor_info['last_ranking']                

                                current_ranking = current_data['data'].get('arenaRanking')

                # 获取当前数据                if current_ranking is None:

                current_data = await self.fetch_arena_data(server, friend_code)                    logger.warning(f"用户 {umo} 获取的数据中没有arenaRanking字段")

                if not current_data or 'data' not in current_data:                    await asyncio.sleep(300)

                    logger.warning(f"用户 {umo} 获取竞技场数据失败")                    continue

                    await asyncio.sleep(300)  # 5分钟后重试                

                    continue                # 检查排名变化

                                if last_ranking is not None and current_ranking != last_ranking:

                current_ranking = current_data['data'].get('arenaRanking')                    # 发送变化通知

                if current_ranking is None:                    await self.send_ranking_change_notification(umo, last_ranking, current_ranking, server)

                    logger.warning(f"用户 {umo} 获取的数据中没有arenaRanking字段")                

                    await asyncio.sleep(300)                # 更新排名

                    continue                self.user_monitors[umo]['last_ranking'] = current_ranking

                                await self.save_monitors_data()

                # 检查排名变化                

                if last_ranking is not None and current_ranking != last_ranking:                logger.info(f"用户 {umo} 排名检查完成: {current_ranking}")

                    # 发送变化通知                

                    await self.send_ranking_change_notification(umo, last_ranking, current_ranking, server)                # 等待5分钟

                                await asyncio.sleep(300)

                # 更新排名                

                self.user_monitors[umo]['last_ranking'] = current_ranking            except asyncio.CancelledError:

                await self.save_monitors_data()                logger.info(f"用户 {umo} 监控任务被取消")

                                break

                logger.info(f"用户 {umo} 排名检查完成: {current_ranking}")            except Exception as e:

                                logger.error(f"用户 {umo} 监控任务执行异常: {str(e)}")

                # 等待5分钟                await asyncio.sleep(60)  # 出错时等待1分钟

                await asyncio.sleep(300)

                    async def send_ranking_change_notification(self, umo: str, old_ranking: int, new_ranking: int, server: str):

            except asyncio.CancelledError:        """发送排名变化通知"""

                logger.info(f"用户 {umo} 监控任务被取消")        try:

                break            # 构建通知消息

            except Exception as e:            if new_ranking < old_ranking:

                logger.error(f"用户 {umo} 监控任务执行异常: {str(e)}")                emoji = "📈"

                await asyncio.sleep(60)  # 出错时等待1分钟                change_text = "上升"

            else:

    async def send_ranking_change_notification(self, umo: str, old_ranking: int, new_ranking: int, server: str):                emoji = "📉"

        """发送排名变化通知"""                change_text = "下降"

        try:            

            # 构建通知消息            message = f"{emoji} BA竞技场排名变化通知\n"

            if new_ranking < old_ranking:            message += f"服务器: {server}\n"

                emoji = "📈"            message += f"排名{change_text}: {old_ranking} → {new_ranking}\n"

                change_text = "上升"            message += f"变化: {abs(new_ranking - old_ranking)} 位"

            else:            

                emoji = "📉"            # 发送消息到原会话

                change_text = "下降"            from astrbot.api.event import MessageChain

                        import astrbot.api.message_components as Comp

            message = f"{emoji} BA竞技场排名变化通知\n"            

            message += f"服务器: {server}\n"            message_chain = MessageChain()

            message += f"排名{change_text}: {old_ranking} → {new_ranking}\n"            message_chain.chain = [Comp.Plain(message)]

            message += f"变化: {abs(new_ranking - old_ranking)} 位"            

                        success = await self.context.send_message(umo, message_chain)

            # 发送消息到原会话            if success:

            from astrbot.api.event import MessageChain                logger.info(f"成功发送排名变化通知到 {umo}")

            import astrbot.api.message_components as Comp            else:

                            logger.error(f"发送排名变化通知失败: {umo}")

            message_chain = MessageChain()                

            message_chain.chain = [Comp.Plain(message)]        except Exception as e:

                        logger.error(f"发送排名变化通知时发生异常: {str(e)}")

            success = await self.context.send_message(umo, message_chain)        """获取竞技场数据"""

            if success:        try:

                logger.info(f"成功发送排名变化通知到 {umo}")            payload = {

            else:                "server": self.server,

                logger.error(f"发送排名变化通知失败: {umo}")                "friendCode": self.friend_code

                            }

        except Exception as e:            

            logger.error(f"发送排名变化通知时发生异常: {str(e)}")            timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=timeout) as session:

    async def terminate(self):                async with session.post(

        """插件销毁方法"""                    "https://bacrawl.diyigemt.com/api/v1/friendsearch",

        try:                    json=payload,

            # 取消所有监控任务                    headers={'Content-Type': 'application/json'}

            for umo, monitor_info in self.user_monitors.items():                ) as response:

                if monitor_info['task'] and not monitor_info['task'].done():                    if response.status == 200:

                    monitor_info['task'].cancel()                        data = await response.json()

                    try:                        return data

                        await monitor_info['task']                    else:

                    except asyncio.CancelledError:                        logger.error(f"获取BA竞技场数据失败，状态码: {response.status}")

                        pass                        return None

                    except Exception as e:

            # 保存数据            logger.error(f"获取BA竞技场数据异常: {str(e)}")

            await self.save_monitors_data()            return None

            

            logger.info("BA PVP Tool: 插件已停止，所有监控任务已取消")    async def load_last_data(self):

        except Exception as e:        """加载上次保存的数据"""

            logger.error(f"插件销毁时发生异常: {str(e)}")        try:
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

    async def send_startup_message(self):
        """发送插件启动消息"""
        try:
            # 首先尝试获取当前排名
            current_data = await self.fetch_arena_data()
            current_ranking = None
            if current_data and 'data' in current_data:
                current_ranking = current_data['data'].get('arenaRanking')
            
            # 构建启动消息
            message = f"🎮 BA竞技场监控插件已启动！\n"
            message += f"服务器: {self.server}\n"
            
            if current_ranking is not None:
                message += f"当前排名: {current_ranking}\n"
                if self.last_arena_ranking is not None:
                    message += f"上次记录: {self.last_arena_ranking}\n"
                else:
                    message += f"首次运行，已记录当前排名\n"
            else:
                message += f"暂时无法获取排名数据\n"
                
            message += f"监控频率: 每5分钟检查一次\n"
            message += f"如有排名变化将及时通知您"
            
            # 构建会话标识 - 使用aiocqhttp平台的私聊格式
            unified_msg_origin = f"aiocqhttp:FRIEND_MESSAGE:{self.notice_id}"
            
            # 发送消息
            from astrbot.api.event import MessageChain
            import astrbot.api.message_components as Comp
            
            message_chain = MessageChain()
            message_chain.chain = [Comp.Plain(message)]
            
            success = await self.context.send_message(unified_msg_origin, message_chain)
            if success:
                logger.info(f"成功发送启动消息到 {self.notice_id}")
            else:
                logger.error(f"发送启动消息失败，可能找不到对应的消息平台")
                
        except Exception as e:
            logger.error(f"发送启动消息时发生异常: {str(e)}")

    async def send_initialization_message(self, ranking: int, full_data: Dict[str, Any]):
        """发送插件初始化成功消息（首次运行时）"""
        try:
            # 构建初始化消息
            message = f"� BA竞技场监控插件首次运行！\n"
            message += f"服务器: {self.server}\n"
            message += f"当前排名: {ranking}\n"
            message += f"已设置为监控基准排名\n"
            message += f"监控频率: 每5分钟检查一次\n"
            message += f"如有排名变化将及时通知您"
            
            # 构建会话标识 - 使用aiocqhttp平台的私聊格式
            unified_msg_origin = f"aiocqhttp:FRIEND_MESSAGE:{self.notice_id}"
            
            # 发送消息
            from astrbot.api.event import MessageChain
            import astrbot.api.message_components as Comp
            
            message_chain = MessageChain()
            message_chain.chain = [Comp.Plain(message)]
            
            success = await self.context.send_message(unified_msg_origin, message_chain)
            if success:
                logger.info(f"成功发送首次运行消息到 {self.notice_id}")
            else:
                logger.error(f"发送首次运行消息失败，可能找不到对应的消息平台")
                
        except Exception as e:
            logger.error(f"发送首次运行消息时发生异常: {str(e)}")

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
            unified_msg_origin = f"aiocqhttp:FRIEND_MESSAGE:{self.notice_id}"
            
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
