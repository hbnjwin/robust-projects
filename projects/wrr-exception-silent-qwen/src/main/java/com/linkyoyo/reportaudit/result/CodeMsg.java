package com.linkyoyo.reportaudit.result;

import lombok.Getter;

/**
 * 错误码 + 消息模板持有者
 * 用于在全局异常处理器中构建结构化错误响应
 */
@Getter
public class CodeMsg {

    private final int code;
    private final String msg;

    public CodeMsg(int code, String msg) {
        this.code = code;
        this.msg = msg;
    }

    /**
     * 用参数填充消息模板中的占位符 (%s)
     *
     * @param args 填充参数
     * @return 新的 CodeMsg 实例，消息已替换
     */
    public CodeMsg fillArgs(Object... args) {
        String filledMsg = String.format(this.msg, args);
        return new CodeMsg(this.code, filledMsg);
    }

    // ---- 预定义错误码常量 ----

    /** 参数校验失败 */
    public static final CodeMsg BIND_ERROR = new CodeMsg(400, "参数校验失败: %s");

    /** 缺少请求参数 */
    public static final CodeMsg MISSING_PARAMETER_ERROR = new CodeMsg(400, "缺少必要参数: %s");

    /** 反射操作异常 */
    public static final CodeMsg REFLECTIVE_ERROR = new CodeMsg(500, "系统内部反射操作异常");

    /** 文件上传失败 */
    public static final CodeMsg FILE_UPLOAD_ERROR = new CodeMsg(400, "文件上传失败: %s");

    /** 服务器内部错误 */
    public static final CodeMsg SERVER_ERROR = new CodeMsg(500, "服务器内部错误，请稍后重试");
}
