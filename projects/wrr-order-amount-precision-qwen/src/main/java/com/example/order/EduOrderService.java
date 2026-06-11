package com.example.order;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class EduOrderService extends ServiceImpl<EduOrderMapper, EduOrderDO> {

    public List<EduOrderDO> listByUserId(Long userId) {
        return lambdaQuery().eq(EduOrderDO::getUserId, userId).list();
    }
}
