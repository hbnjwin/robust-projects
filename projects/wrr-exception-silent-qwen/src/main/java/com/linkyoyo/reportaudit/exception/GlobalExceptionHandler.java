package com.linkyoyo.reportaudit.exception;


import com.linkyoyo.reportaudit.result.CodeMsg;
import com.linkyoyo.reportaudit.result.R;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Controller;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MultipartException;

import javax.validation.ConstraintViolation;
import javax.validation.ConstraintViolationException;
import java.util.List;
import java.util.Set;

@ControllerAdvice(annotations = Controller.class)
@Slf4j
public class GlobalExceptionHandler {

    /**
     * bean参数校验未通过异常
     */
    @ExceptionHandler(BindException.class)
    @ResponseBody
    private R bindException(BindException e) {

        return R.error(CodeMsg.BIND_ERROR.fillArgs(buildErrorMsg(e.getBindingResult().getFieldErrors())));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseBody
    private R methodArgumentNotValidException(MethodArgumentNotValidException e) {

        return R.error(CodeMsg.BIND_ERROR.fillArgs(buildErrorMsg(e.getBindingResult().getFieldErrors())));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    @ResponseBody
    private R constraintViolationException(ConstraintViolationException e) {


        StringBuilder sb = new StringBuilder();

        String separator = ",";
        Set<ConstraintViolation<?>> constraintViolations = e.getConstraintViolations();

        for (ConstraintViolation<?> constraintViolation : constraintViolations) {

            sb.append(constraintViolation.getMessage()).append(separator);

        }

        String msg = sb.deleteCharAt(sb.length() - separator.length()).toString();

        return R.error(CodeMsg.BIND_ERROR.fillArgs(msg));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    @ResponseBody
    private R constraintViolationException(MethodArgumentTypeMismatchException e) {


        String msg = String.format("%s 类型转换异常", e.getName());

        return R.error(CodeMsg.BIND_ERROR.fillArgs(msg));
    }


    @ExceptionHandler(MissingServletRequestParameterException.class)
    @ResponseBody
    private R missingServletRequestParameterException(MissingServletRequestParameterException e) {

        CodeMsg codeMsg = CodeMsg.MISSING_PARAMETER_ERROR.fillArgs(e.getParameterName());

        return R.error(codeMsg);
    }

    @ExceptionHandler(ReflectiveOperationException.class)
    @ResponseBody
    private R reflectiveOperationException(ReflectiveOperationException e) {

        log.error(CodeMsg.REFLECTIVE_ERROR.getMsg(), e);

        return R.error(CodeMsg.REFLECTIVE_ERROR);
    }

    @ExceptionHandler(MultipartException.class)
    @ResponseBody
    private R multipartException(MultipartException e) {

        log.error(CodeMsg.FILE_UPLOAD_ERROR.fillArgs(e.getMessage()).getMsg(), e);

        return R.error(CodeMsg.FILE_UPLOAD_ERROR.fillArgs(e.getMessage()));
    }



    @ExceptionHandler(EntityNotFoundException.class)
    @ResponseBody
    private ResponseEntity<R> entityNotFoundException(EntityNotFoundException e) {
        log.warn("实体未找到: {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(R.error(new CodeMsg(404, e.getMessage())));
    }

    @ExceptionHandler(ServiceUnavailableException.class)
    @ResponseBody
    private ResponseEntity<R> serviceUnavailableException(ServiceUnavailableException e) {
        log.error("外部服务不可用: {}", e.getMessage(), e);
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(R.error(new CodeMsg(503, e.getMessage())));
    }

    @ExceptionHandler(InvalidInputException.class)
    @ResponseBody
    private ResponseEntity<R> invalidInputException(InvalidInputException e) {
        log.warn("无效输入: {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(R.error(new CodeMsg(400, e.getMessage())));
    }

    @ExceptionHandler(BizException.class)
    @ResponseBody
    private R bizException(BizException e) {
        return R.error(e.getCodeMsg());
    }

    @ExceptionHandler(Exception.class)
    @ResponseBody
    private R exception(Exception e) {

        log.error("未处理异常", e);
        return R.error(CodeMsg.SERVER_ERROR);
    }


    private String buildErrorMsg(List<FieldError> fieldErrors) {

        StringBuilder sb = new StringBuilder();

        String separator = ",";

        for (FieldError fieldError : fieldErrors) {
            // 参数转换异常
            if ("typeMismatch".equals(fieldError.getCode())) {
                sb.append(fieldError.getField()).append(" 类型转换异常").append(separator);
            } else {
                sb.append(fieldError.getField()).append(" ").append(fieldError.getDefaultMessage()).append(separator);
            }
        }

        return sb.deleteCharAt(sb.length() - separator.length()).toString();
    }
}
