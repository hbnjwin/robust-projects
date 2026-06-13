package com.linkyoyo.reportaudit.exception;

import com.linkyoyo.reportaudit.result.CodeMsg;
import lombok.Getter;

/**
 * 业务逻辑异常基类
 * 所有业务层的已知异常均应继承此类，携带结构化错误码信息，
 * 由 GlobalExceptionHandler 统一拦截并转换为标准错误响应。
 */
@Getter
public class BizException extends RuntimeException {

    private final CodeMsg codeMsg;

    public BizException(CodeMsg codeMsg) {
        super(codeMsg.getMsg());
        this.codeMsg = codeMsg;
    }

    public BizException(CodeMsg codeMsg, Throwable cause) {
        super(codeMsg.getMsg(), cause);
        this.codeMsg = codeMsg;
    }
}
