"""
京东帮助中心 FAQ 爬虫
采集退换货/退款/物流/售后/支付等常见问题，输出为 knowledge/*.md
"""
import re
import time
import json
import requests
from pathlib import Path
from typing import Optional

# 配置文件
OUTPUT_DIR = Path(__file__).parent.parent / "backend" / "data" / "knowledge"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 京东帮助中心各分类
CATEGORIES = {
    "退换货": "https://help.jd.com/user/issue/list-112.html",
    "退款": "https://help.jd.com/user/issue/list-113.html",
    "物流配送": "https://help.jd.com/user/issue/list-114.html",
    "售后维修": "https://help.jd.com/user/issue/list-371.html",
    "支付问题": "https://help.jd.com/user/issue/list-115.html",
    "发票问题": "https://help.jd.com/user/issue/list-132.html",
    "账户问题": "https://help.jd.com/user/issue/list-123.html",
}

# 备用URL：拼多多帮助中心（结构更简单）
PDD_CATEGORIES = {
    "退换货": "https://mms.pinduoduo.com/help/list?type=3",
    "物流配送": "https://mms.pinduoduo.com/help/list?type=4",
}


def fetch_page(url: str, retries: int = 3) -> Optional[str]:
    """带重试的页面抓取"""
    for i in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
            print(f"  [{i+1}] HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [{i+1}] 请求失败: {e}")
        time.sleep(2 * (i + 1))
    return None


def extract_jd_faq(html: str, category: str) -> list[dict]:
    """
    从京东帮助中心页面提取FAQ。
    京东页面结构：<div class="help-detail"> 含 <h3> 标题 + <div class="help-content"> 内容
    """
    faqs = []
    
    # 方式1：匹配 help-detail 块
    blocks = re.findall(
        r'<div[^>]*class="[^"]*help-detail[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL
    )
    
    if not blocks:
        # 方式2：匹配列表中可点击的标题，再解析详情页
        # 京东帮助中心列表页：<a href="/user/issue/xxx.html">标题</a>
        links = re.findall(
            r'<a[^>]*href="(/user/issue/\d+-\d+\.html)"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )
        
        for href, title_raw in links[:30]:  # 每类最多30条
            title = re.sub(r'<[^>]+>', '', title_raw).strip()
            if not title or len(title) < 4:
                continue
            
            detail_url = f"https://help.jd.com{href}"
            detail_html = fetch_page(detail_url)
            if not detail_html:
                continue
            
            # 提取详情页内容
            content_match = re.search(
                r'<div[^>]*class="[^"]*help-content[^"]*"[^>]*>(.*?)</div>',
                detail_html, re.DOTALL
            )
            if content_match:
                content = clean_html(content_match.group(1))
                if len(content) > 20:
                    faqs.append({"title": title, "content": content})
                    print(f"  ✓ {title[:40]}")
            time.sleep(0.5)  # 礼貌延迟
        
        return faqs
    
    # 如果直接匹配到 help-detail 块（少数页面）
    for block in blocks:
        title_match = re.search(r'<h[23][^>]*>(.*?)</h[23]>', block, re.DOTALL)
        content_match = re.search(r'<div[^>]*class="[^"]*help-content[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
        
        if title_match and content_match:
            title = clean_html(title_match.group(1))
            content = clean_html(content_match.group(1))
            if title and len(content) > 20:
                faqs.append({"title": title, "content": content})
                print(f"  ✓ {title[:40]}")
    
    return faqs


def clean_html(text: str) -> str:
    """清理HTML标签和空白"""
    # 移除标签
    text = re.sub(r'<[^>]+>', '', text)
    # 解码实体
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
    # 合并空白
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def generate_fallback_faq(category: str) -> list[dict]:
    """爬取失败时，用AI生成高质量FAQ作为兜底"""
    # 这里不实际调AI，返回空让外层统一处理
    return []


ALL_FALLBACK_FAQS = {
    "退换货": [
        {"title": "退货申请流程是怎样的？", "content": "进入「我的订单」-找到对应订单-点击「申请售后」-选择「退货退款」-填写退货原因并上传凭证-提交申请。商家会在48小时内审核，审核通过后系统会发送退货地址。寄回商品后，商家签收确认无误，退款会在3-7个工作日内退回原支付方式。"},
        {"title": "哪些商品不支持7天无理由退货？", "content": "以下商品不支持7天无理由退货：1）消费者定制的商品；2）鲜活易腐商品；3）在线下载或已拆封的数字化商品；4）交付的报纸期刊；5）拆封后影响人身安全或生命健康的商品（如食品、保健品、化妆品等）；6）一经激活或试用后价值贬损较大的商品（如手机、电脑等数码产品）；7）临近保质期的商品；8）已拆封的包装耗材（如胶带、气泡膜等）。具体请以商品详情页标注为准。"},
        {"title": "退货的运费由谁承担？", "content": "运费承担规则如下：1）因商品质量问题、发错货、商品与描述不符等原因导致的退货，商家承担来回运费；2）7天无理由退货，买家自行承担退货运费；3）双方协商一致的退货，按协商结果执行。建议寄回时使用有物流跟踪的快递，并保留快递单号。"},
        {"title": "退货后多久能收到退款？", "content": "退款到账时间取决于支付方式：1）微信支付：商家确认收货后1-3个工作日到账；2）支付宝：商家确认收货后1-3个工作日；3）银行卡：商家确认收货后3-7个工作日；4）京东白条/金条：恢复额度即时生效；5）京东E卡/礼品卡：即时退回账户余额。如超时未到账，请联系客服查询。"},
        {"title": "换货的流程是什么？", "content": "换货流程：1）进入订单详情，点击「申请售后」-「换货」；2）选择换货原因并上传商品照片；3）商家审核（通常24小时内）；4）审核通过后，将商品寄回给商家；5）商家收到后确认无误，发出新商品。整个换货周期通常需要5-10个工作日。注意：换货仅支持同款同色同码，如需更换其他款式需先退货再重新下单。"},
        {"title": "收到商品有质量问题怎么退货？", "content": "收到商品如有质量问题，请在签收后24小时内联系客服处理。需要提供清晰的商品照片或视频作为凭证，包括：整体照片、问题部位特写、外包装照片、快递面单照片。客服确认后，会安排退货或换货，运费由商家承担。逾期未反馈可能影响售后处理。"},
    ],
    "退款": [
        {"title": "退款什么时候到账？", "content": "退款到账时间：1）微信支付/支付宝：商家确认退款后1-3个工作日；2）银行卡：3-7个工作日；3）京东白条：即时恢复额度；4）京东支付余额：即时到账；5）货到付款现金退款：需提供银行卡信息，3-7个工作日到账。如超过上述时效，请联系客服并提供订单号查询。"},
        {"title": "部分退款怎么操作？", "content": "部分退款适用于以下场景：1）购买多件商品只退其中部分；2）商品降价申请价保补差；3）商品缺货部分退款。操作方式：进入订单详情页-申请售后-选择「仅退款」-填写退款金额和原因-提交申请。商家审核通过后，按比例退回对应金额。"},
        {"title": "取消订单后多久退款？", "content": "取消订单退款时效：1）未付款订单取消：无需退款；2）已付款未发货取消：商家确认后1-3个工作日到账；3）已发货申请拦截：需联系客服，拦截成功后3-7个工作日退款。春节期间或大促期间可能延迟，具体以支付渠道为准。"},
        {"title": "退款金额不对怎么办？", "content": "退款金额异常处理：1）使用了优惠券/红包，退款时按比例退回；2）参与了满减活动，部分退款后可能不满足满减条件，实际退款金额会扣除优惠部分；3）使用了京豆/E卡支付，优先退回原支付方式。如对退款金额有疑问，联系客服提供订单号核查。"},
        {"title": "货到付款怎么退款？", "content": "货到付款订单退款流程：1）在订单页面申请退货退款；2）商家审核通过后，您需要提供收款银行卡信息（开户行、卡号、户名）；3）商家收到退货确认后，退款在3-7个工作日打入您提供的银行卡。部分自营商品支持退回京东余额。"},
    ],
    "物流配送": [
        {"title": "如何查询物流信息？", "content": "查询物流有3种方式：1）京东APP-我的-我的订单-点击对应订单「查看物流」；2）京东官网-我的订单-订单详情-物流信息；3）复制快递单号到快递100或对应快递公司官网查询。物流信息通常在发货后2-4小时首次更新。如超过24小时无更新，请联系客服。"},
        {"title": "一般多久能收到货？", "content": "配送时效：1）京东自营：当日上午11点前下单，当日送达（限京东211限时达覆盖区域）；当日晚间11点前下单，次日15点前送达；2）第三方商家：通常2-5个工作日；3）大件商品（家电、家具）：3-7个工作日，含送货上门和安装；4）偏远地区：5-10个工作日。具体时效以商品页面和下单时系统提示为准。"},
        {"title": "物流长时间不更新怎么办？", "content": "物流不更新的处理方案：1）发货后24小时内未更新属于正常，请耐心等待；2）超过48小时未更新，先联系商家确认是否已真实发货；3）超过72小时无物流更新，可申请「未收到货」退款或要求商家补发；4）大促期间（618、双11）物流可能延迟3-5天。保留好订单编号和沟通记录。"},
        {"title": "快递显示签收但没收到货？", "content": "若快递显示已签收但您实际未收到，请按以下步骤处理：1）检查是否被家人/同事/前台/快递柜代收；2）查看快递柜是否有取件码短信（可能被拦截）；3）联系快递员核实投递情况；4）若确认丢失，联系商家或快递公司索赔。建议在签收状态变更后24小时内反馈，超时可能无法调取监控。"},
        {"title": "可以修改收货地址吗？", "content": "修改地址规则：1）未发货订单：可直接在订单详情页修改地址；2）已发货订单：联系客服尝试拦截或转寄，可能产生额外运费；3）货到付款订单修改地址需重新验证。大促期间修改地址可能导致发货延迟，请谨慎操作。以下情况无法修改：跨境订单已清关、生鲜已出库、定制商品已生产。"},
    ],
    "售后维修": [
        {"title": "商品坏了怎么申请维修？", "content": "维修申请流程：1）进入「我的订单」-找到对应订单-「申请售后」-选择「维修」；2）描述故障现象并上传商品照片/视频；3）客服审核（24小时内），确认是否在保修范围；4）审核通过后按指引寄回商品；5）工程师检测后确定维修方案；6）维修完成寄回。质保期内非人为损坏免费维修。"},
        {"title": "保修期是多久？", "content": "不同品类保修期不同：1）手机/电脑/平板：主机保修1年，配件（电池/充电器）保修6个月；2）大家电（冰箱/洗衣机/空调）：整机保修1年，主要部件保修3年；3）小家电：整机保修1年；4）服装鞋包：无保修，签收7天内质量问题可退换；5）食品/保健品：不支持保修。保修期从签收之日起算，以快递签收记录为准。"},
        {"title": "哪些情况不保修？", "content": "以下情况不在免费保修范围：1）超出保修期限；2）人为损坏（摔坏、进水、挤压、自行拆修、使用非原装配件）；3）不可抗力因素（火灾、水灾、雷击等）；4）无法提供有效购买凭证；5）商品序列号被涂改或撕毁；6）未按说明书要求使用、维护、保管造成的损坏；7）消耗性部件（电池、滤芯、灯泡）的正常损耗。"},
        {"title": "维修大概需要多久？", "content": "维修周期：1）手机/平板：7-15个工作日（寄修含往返物流时间）；2）电脑：10-20个工作日；3）大家电：上门维修通常3-5个工作日安排上门；4）小家电：5-10个工作日。以上为常规时效，具体以售后检测结果为准。如需等配件可能延长。维修进度可在「售后服务单」中实时查询。"},
    ],
    "支付问题": [
        {"title": "支持哪些支付方式？", "content": "京东支持以下支付方式：1）微信支付；2）支付宝；3）银行卡（储蓄卡/信用卡）；4）京东支付（余额/白条/金条）；5）Apple Pay（iOS端）；6）云闪付；7）货到付款（部分商品支持）；8）京东E卡/礼品卡；9）数字人民币（试点区域）；10）企业转账（企业用户）。具体以收银台展示为准。"},
        {"title": "支付失败怎么办？", "content": "支付失败排查步骤：1）确认银行卡余额充足或信用额度未超；2）检查是否开通了网上支付功能（部分银行卡需要单独开通）；3）确认单笔/单日支付限额未超；4）尝试更换支付方式或网络环境；5）清除京东APP缓存后重试。如多次失败，联系银行确认卡片状态，或联系京东客服协助处理。"},
        {"title": "如何申请发票？", "content": "申请发票：1）下单时在结算页面勾选「开具发票」；2）已完成的订单可在「我的订单」-订单详情-「申请发票」补开；3）支持电子发票和纸质发票（部分品类仅支持电子发票）；4）电子发票在申请后24小时内发送到预留邮箱；5）纸质发票随包裹寄出或单独邮寄。发票抬头可选择个人或企业（需提供税号）。发票开具时间限制：订单完成后30天内可补开。"},
    ],
    "账户问题": [
        {"title": "忘记密码怎么办？", "content": "找回密码：1）在登录页面点击「忘记密码」；2）输入绑定的手机号或邮箱；3）接收验证码；4）设置新密码（8-20位，含数字+字母）；5）重新登录。如果绑定的手机号已停用，需要联系客服进行人工身份验证，提供：注册手机号、常用收货地址、近期订单号等信息。"},
        {"title": "如何修改绑定手机号？", "content": "修改绑定手机号：1）登录后在「我的」-「设置」-「账户安全」-「修改手机号」；2）输入原手机号接收验证码（如原手机号可用）；3）输入新手机号接收验证码；4）完成修改。如原手机号无法接收验证码，需联系客服进行人工审核，需提供身份证照片和近期订单信息。"},
        {"title": "账号被冻结怎么办？", "content": "账号冻结处理：1）登录时系统会提示冻结原因（如异常登录、违规操作等）；2）根据提示进行身份验证（手机验证码/人脸识别）；3）如因安全原因冻结，验证后自动解冻；4）如因违规被冻结，需联系客服了解具体原因并申请解冻。恶意刷单、虚假交易等严重违规行为可能导致永久封禁。"},
    ],
}


def main():
    print("=" * 60)
    print("京东帮助中心 FAQ 采集")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_faqs = {}
    
    for category, url in CATEGORIES.items():
        print(f"\n📂 分类: {category}")
        print(f"   URL: {url}")
        
        html = fetch_page(url)
        if not html:
            print(f"  ⚠ 页面抓取失败，使用备用数据")
            faqs = ALL_FALLBACK_FAQS.get(category, [])
        else:
            faqs = extract_jd_faq(html, category)
            if len(faqs) < 3:
                print(f"  ⚠ 仅提取到 {len(faqs)} 条，补全备用数据")
                fallback = ALL_FALLBACK_FAQS.get(category, [])
                # 合并去重（按标题）
                existing_titles = {f["title"] for f in faqs}
                for fb in fallback:
                    if fb["title"] not in existing_titles and len(faqs) < 8:
                        faqs.append(fb)
        
        print(f"  📊 共 {len(faqs)} 条FAQ")
        all_faqs[category] = faqs
    
    # 写入 md 文件
    total = 0
    for category, faqs in all_faqs.items():
        if not faqs:
            continue
        
        # 文件名用拼音
        file_map = {
            "退换货": "returns", "退款": "refunds", "物流配送": "logistics",
            "售后维修": "warranty", "支付问题": "payment", "发票问题": "invoice",
            "账户问题": "account",
        }
        filename = file_map.get(category, category)
        md_path = OUTPUT_DIR / f"{filename}.md"
        
        lines = ["# 电商客服常见问题 — {}\n".format(category)]
        for faq in faqs:
            lines.append(f"\n## {faq['title']}\n")
            lines.append(f"{faq['content']}\n")
        
        md_path.write_text("\n".join(lines), encoding="utf-8")
        total += len(faqs)
        print(f"\n✅ 已写入: {filename}.md ({len(faqs)}条)")
    
    print(f"\n{'=' * 60}")
    print(f"总计: {total} 条FAQ，{len(all_faqs)} 个分类")
    print(f"输出目录: {OUTPUT_DIR}")
    
    # 保留原有 faq.md 备份
    old_faq = OUTPUT_DIR / "faq.md"
    if old_faq.exists():
        backup = OUTPUT_DIR / "faq_old_backup.md"
        old_faq.rename(backup)
        print(f"📦 原 faq.md 已备份为 faq_old_backup.md")


if __name__ == "__main__":
    main()
