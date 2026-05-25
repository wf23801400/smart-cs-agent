-- ============================================
-- Mock 数据 (与现有 order_mock.json 对应)
-- ============================================

USE smart_cs_agent;

-- 测试用户
INSERT INTO users (id, user_name, phone, email) VALUES
(1, '张三', '13800001001', 'zhangsan@example.com'),
(2, '李四', '13800001002', 'lisi@example.com'),
(3, '王五', '13800001003', 'wangwu@example.com');

-- 测试订单
INSERT INTO orders (order_id, user_id, product_name, price, status, created_at) VALUES
('ORD-001', 1, '无线蓝牙耳机 Pro',   299.00,  '已发货', '2024-05-20 14:30:00'),
('ORD-002', 2, '夏季休闲T恤 白色 L码', 89.00,  '待付款', '2024-05-21 09:15:00'),
('ORD-003', 1, '智能手表 Ultra',     1299.00, '已完成', '2024-05-15 11:00:00'),
('ORD-004', 3, '折叠便携键盘',        199.00,  '已退款', '2024-05-10 16:45:00'),
('ORD-005', 2, '天然乳胶枕 一对装',   399.00,  '已发货', '2024-05-22 08:00:00');

-- 测试物流
INSERT INTO logistics (order_id, company, tracking_no, status, current_location, estimated_delivery) VALUES
('ORD-001', '顺丰速运', 'SF1234567890', '运输中', '已到达【北京分拣中心】', '2024-05-23'),
('ORD-005', '中通快递', 'ZT5678901234', '已揽收', '【深圳龙华营业部】已揽收', '2024-05-25'),
('ORD-003', '圆通快递', 'YT9876543210', '已签收', '已签收，签收人：本人签收', '2024-05-18');
