package com.linkyoyo.reportaudit.exception;

import com.linkyoyo.reportaudit.result.CodeMsg;
import lombok.Getter;

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
