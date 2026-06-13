package com.linkyoyo.reportaudit.result;

import lombok.Getter;
import lombok.Setter;

/**
 * 统一 API 响应包装类
 * 所有 Controller 返回值均通过此类包装，保持前后端接口格式一致
 */
@Getter
@Setter
public class R {

    private int code;
    private String msg;
    private Object data;

    private R() {}

    private R(int code, String msg, Object data) {
        this.code = code;
        this.msg = msg;
        this.data = data;
    }

    /**
     * 成功响应（带数据）
     */
    public static R ok(Object data) {
        return new R(200, "success", data);
    }

    /**
     * 成功响应（仅消息）
     */
    public static R ok(String msg) {
        return new R(200, msg, null);
    }

    /**
     * 错误响应（基于 CodeMsg）
     */
    public static R error(CodeMsg codeMsg) {
        return new R(codeMsg.getCode(), codeMsg.getMsg(), null);
    }

    /**
     * 错误响应（纯字符串消息，默认 code=500）
     */
    public static R error(String msg) {
        return new R(500, msg, null);
    }

    /**
     * 警告响应（code=200 但携带提示消息）
     */
    public static R warning(String msg) {
        return new R(200, msg, null);
    }
}
