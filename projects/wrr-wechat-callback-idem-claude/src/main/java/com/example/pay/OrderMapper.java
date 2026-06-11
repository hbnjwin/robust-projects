package com.example.pay;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface OrderMapper {
    @Select("SELECT * FROM edu_order WHERE order_no = #{orderNo}")
    OrderDO selectByOrderNo(String orderNo);

    void updateById(OrderDO order);
}
