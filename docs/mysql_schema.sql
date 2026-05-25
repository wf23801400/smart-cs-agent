-- ============================================
-- 智能客服系统 MySQL 建表脚本
-- 数据库名: smart_cs_agent
-- ============================================

CREATE DATABASE IF NOT EXISTS smart_cs_agent
  DEFAULT CHARSET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE smart_cs_agent;

-- -------------------------------------------
-- 1. 用户表
-- -------------------------------------------
CREATE TABLE users (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_name  VARCHAR(100)  NOT NULL        COMMENT '用户名/昵称',
    phone      VARCHAR(20)   DEFAULT NULL    COMMENT '手机号',
    email      VARCHAR(200)  DEFAULT NULL    COMMENT '邮箱',
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_phone (phone),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- -------------------------------------------
-- 2. 会话表
-- -------------------------------------------
CREATE TABLE sessions (
    id         VARCHAR(32) PRIMARY KEY        COMMENT '会话ID (uuid前8位)',
    user_id    BIGINT      DEFAULT NULL       COMMENT '关联用户',
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话表';

-- -------------------------------------------
-- 3. 消息表 (对话历史)
-- -------------------------------------------
CREATE TABLE messages (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL            COMMENT '会话ID',
    role       ENUM('user','assistant') NOT NULL COMMENT '角色',
    content    TEXT        NOT NULL            COMMENT '消息内容',
    intent     VARCHAR(20) DEFAULT NULL        COMMENT '意图分类',
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息历史表';

-- -------------------------------------------
-- 4. 订单表
-- -------------------------------------------
CREATE TABLE orders (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id     VARCHAR(32)  NOT NULL UNIQUE  COMMENT '订单号 (如 ORD-001)',
    user_id      BIGINT       DEFAULT NULL     COMMENT '用户ID',
    product_name VARCHAR(200) NOT NULL         COMMENT '商品名称',
    price        DECIMAL(10,2) NOT NULL        COMMENT '金额',
    status       VARCHAR(20)  NOT NULL DEFAULT '待付款' COMMENT '订单状态',
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

-- -------------------------------------------
-- 5. 物流表
-- -------------------------------------------
CREATE TABLE logistics (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id            VARCHAR(32)  NOT NULL  COMMENT '订单号',
    company             VARCHAR(50)  DEFAULT NULL COMMENT '快递公司',
    tracking_no         VARCHAR(50)  DEFAULT NULL COMMENT '运单号',
    status              VARCHAR(20)  DEFAULT NULL COMMENT '物流状态',
    current_location    VARCHAR(200) DEFAULT NULL COMMENT '当前位置',
    estimated_delivery  DATE         DEFAULT NULL COMMENT '预计送达',
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_order (order_id),
    INDEX idx_tracking (tracking_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='物流表';

-- -------------------------------------------
-- 6. 工单表
-- -------------------------------------------
CREATE TABLE tickets (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticket_id    VARCHAR(32) NOT NULL UNIQUE   COMMENT '工单号 (如 TKT-20240524-001)',
    session_id   VARCHAR(32) DEFAULT NULL      COMMENT '关联会话',
    user_message TEXT        NOT NULL          COMMENT '用户原始消息',
    order_id     VARCHAR(32) DEFAULT NULL      COMMENT '关联订单号',
    intent       VARCHAR(20) DEFAULT 'general' COMMENT '意图类型',
    severity     VARCHAR(10) DEFAULT 'medium'  COMMENT '严重等级: low/medium/high',
    status       VARCHAR(20) DEFAULT 'open'    COMMENT '工单状态: open/closed',
    created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_order (order_id),
    INDEX idx_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单表';

-- -------------------------------------------
-- 7. 反馈表
-- -------------------------------------------
CREATE TABLE feedback (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id  VARCHAR(32) NOT NULL            COMMENT '会话ID',
    reply_index INT         NOT NULL            COMMENT '回复序号',
    rating      ENUM('up','down') NOT NULL      COMMENT '评价',
    created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户反馈表';
