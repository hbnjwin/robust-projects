package com.linkyoyo.reportaudit.support;

import cn.hutool.core.collection.CollectionUtil;
import cn.hutool.core.date.DateUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.azure.ai.openai.OpenAIClient;
import com.azure.ai.openai.OpenAIClientBuilder;
import com.azure.ai.openai.OpenAIServiceVersion;
import com.azure.ai.openai.models.*;
import com.azure.core.credential.AzureKeyCredential;
import com.azure.core.util.IterableStream;
import com.github.wenhao.jpa.PredicateBuilder;
import com.github.wenhao.jpa.Specifications;
import com.google.common.collect.Lists;
import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.config.LinkyoyoAiConfig;
import com.linkyoyo.reportaudit.query.CommonQueryInfo;
import com.linkyoyo.reportaudit.util.llm.HttpClientFactory;
import com.linkyoyo.reportaudit.util.llm.LinkyoyoRequestBuilder;
import com.querydsl.jpa.impl.JPAQueryFactory;
//import com.squareup.okhttp.*;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.apache.commons.collections.CollectionUtils;
import org.hibernate.query.NativeQuery;
import org.hibernate.transform.Transformers;
import org.mvel2.MVEL;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.util.concurrent.TimeUnit;

import javax.persistence.EntityManager;
import javax.persistence.EntityManagerFactory;
import javax.persistence.Query;
import java.io.*;
import java.lang.reflect.Field;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.stream.Collectors;




@Component
@Slf4j
public class CommonFunc {

    private static AiConfig aiConfig;

    public static LinkyoyoAiConfig linkyoyoAiConfig;

    @Autowired
    public void setAiConfig(AiConfig aiConfig) {
        CommonFunc.aiConfig = aiConfig;
    }

    @Autowired
    public void setLinkyoyoAiConfig(LinkyoyoAiConfig linkyoyoAiConfig) {
        CommonFunc.linkyoyoAiConfig = linkyoyoAiConfig;
    }

    private static HttpClientFactory httpClientFactory;

    @Autowired
    public void setHttpClientFactory(HttpClientFactory factory) {
        CommonFunc.httpClientFactory = factory;
    }

    @Autowired
    private JPAQueryFactory jpaQueryFactory;

    @Autowired
    public EntityManagerFactory entityManagerFactory;



//    @Autowired
//    private GetMaxValueRepository getMaxValueRepository ;

    public static void clearEntityManager(EntityManager em) {
       try {
           if (Objects.nonNull(em) )
               em.clear();
       }
       catch(Exception e)
       {
           log.error("clearEntityManager error:{}",e.getMessage());
       }

    }

    public static String getBegindate(String beginDate) {
        if (CommonFunc.getString(beginDate + "@", " ", ":").compareTo("12") < 0) {
            return getString("@" + beginDate, "@", " ") + " 08:00";
        } else {
            return getString("@" + beginDate, "@", " ") + " 20:00";
        }
    }


    //需要注意的是当删除某一目录时，必须保证该目录下没有其他文件才能正确删除，否则将删除失败。
    public static void deleteFolder(File folder) throws Exception {
        if (!folder.exists()) {
            throw new Exception("文件不存在");
        }
        File[] files = folder.listFiles();
        if (files != null) {
            for (File file : files) {
                if (file.isDirectory()) {
                    //递归直到目录下没有文件
                    deleteFolder(file);
                } else {
                    //删除
                    file.delete();
                }
            }
        }
        //删除
        folder.delete();

    }


    /**
     * 按照指定长度切割列表
     *
     * @param list
     * @param groupSize
     * @param <T>
     * @return
     */
    public static <T> List<List<T>> splitList(List<T> list, int groupSize) {
        int length = list.size();
        // 计算可以分成多少组
        int num = (length + groupSize - 1) / groupSize; // TODO
        List<List<T>> newList = new ArrayList<>(num);
        for (int i = 0; i < num; i++) {
            // 开始位置
            int fromIndex = i * groupSize;
            // 结束位置
            int toIndex = (i + 1) * groupSize < length ? (i + 1) * groupSize : length;
            newList.add(list.subList(fromIndex, toIndex));
        }
        return newList;
    }





    public static <T> Specification<T> getWhere(String strWhere, String keyWord, Boolean haveDelFlag) {
        PredicateBuilder<T> specEmp = Specifications.<T>or();
        PredicateBuilder<T> specFlag = Specifications.<T>and();
        if (haveDelFlag) {
            if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
                specFlag.eq("delFlag", false);
                return specFlag.build();

            }
        }

//        String[]  arrIds={"id","deptid","parentid"} ;  //ArrayUtil.contains(arrIds,s.toLowerCase())
        if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
            return specEmp.build();
        }
        if (Objects.isNull(strWhere) || strWhere.trim().equals("")) {
            return specEmp.build();
        }
        List<String> lstWhere = Arrays.asList(strWhere.split(","));
        for (String s : lstWhere) {

            if (s.equals("id") || StrUtil.subSufByLength(s, 2).equals("Id") || StrUtil.subSufByLength(s, 5).equals("Level"))
                specEmp.eq(s, keyWord);
            else
                specEmp.like(s, "%" + keyWord + "%");

        }
        if (haveDelFlag) {
            specFlag.eq("delFlag", false);
            return specFlag.predicate(specEmp.build()).build();

        } else {
            return specEmp.build();
        }


    }

    public static <T> Specification<T> getWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        String strWhere = query.getWhere();
        String keyWord = query.getKeyWord();
        boolean haveDelFlag = false;
        Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
        Class clazz = (Class) params[0];
        // 判断是否含有delFlag字段
        Field field = Arrays.asList(clazz.getDeclaredFields())
                .stream().filter(f -> f.getName().toLowerCase().equals("delflag".toLowerCase())).findFirst().orElse(null);
        if (field != null)
            haveDelFlag = true;

        PredicateBuilder<T> specEmp = Specifications.<T>or();
        PredicateBuilder<T> specFlag = Specifications.<T>and();
        if (haveDelFlag) {
            if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
                specFlag.ne("delFlag", true);
                return specFlag.build();

            }
        }

        if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
            return specEmp.build();
        }
        if (Objects.isNull(strWhere) || strWhere.trim().equals("")) {
            return specEmp.build();
        }
        List<String> lstWhere = Arrays.asList(strWhere.split(","));
        for (String s : lstWhere) {

            field = Arrays.asList(clazz.getDeclaredFields())
                    .stream().filter(f -> f.getName().toLowerCase().equals(s.toLowerCase())).findFirst().orElse(null);

            if (Objects.nonNull(field)) {

                if (field.getType().equals(String.class))
                    specEmp.like(s, "%" + keyWord + "%");
                else
                    specEmp.eq(s, keyWord);
            }

        }
        if (haveDelFlag) {
            specFlag.eq("delFlag", false);
            return specFlag.predicate(specEmp.build()).build();

        } else {
            return specEmp.build();
        }


    }


    public List commQuery(CommonQueryInfo commonQueryInfo) {
        if (Objects.isNull(commonQueryInfo.getTableName()) || Objects.isNull(commonQueryInfo.getFields()))
            return null;
        Boolean haveWhere = false;
        String sql = "select " + commonQueryInfo.getFields() + " from " + commonQueryInfo.getTableName();
        if (Objects.nonNull(commonQueryInfo.getWhere()) && !commonQueryInfo.getWhere().equals("")) {
            sql = sql + " where " + commonQueryInfo.getWhere() + "=?1";
            haveWhere = true;
        }

        if (Objects.nonNull(commonQueryInfo.getSort()) && !commonQueryInfo.getSort().equals("")) {
            sql = sql + " order by " + commonQueryInfo.getSort();
        }
        EntityManager entityManager = entityManagerFactory.createEntityManager();
        Query queryNative = entityManager.createNativeQuery(sql);
        if (haveWhere)
            queryNative = queryNative.setParameter(1, commonQueryInfo.getKeyWord());

        queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
        List rows = queryNative.getResultList();


        return rows;

    }

    public List actQuery(CommonQueryInfo commonQueryInfo) {
        if (Objects.isNull(commonQueryInfo.getSql()))
            return null;
        String sql = commonQueryInfo.getSql();
        EntityManager entityManager = entityManagerFactory.createEntityManager();
        Query queryNative = entityManager.createNativeQuery(sql);
        queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
        List rows = queryNative.getResultList();


        return rows;

    }

    @Transactional(readOnly = true)
    public List commQuerySql(String sql) {

        EntityManager entityManager = entityManagerFactory.createEntityManager();

        Query queryNative = entityManager.createNativeQuery(sql);
       /* if (!entityManager.isOpen())
        {
//            log("connect is disconnected") ;
            throw new BizException(CodeMsg.CALL_SERVICE_ERROR.fillArgs("connect is disconnected！"));
        }*/
        queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);  //ALIAS_TO_ENTITY_MAP TO_LIST
        List rows = queryNative.getResultList();
        entityManager.close();

        return rows;

    }


    /**
     * 调用存储过程获取最大值
     *
     * @param moduleName
     * @return
     */

  /*  public String getModuleMaxValue(String moduleName) {
        String outParam = getMaxValueRepository.getModuleMaxValue(moduleName);
//        Assert.assertEquals(outParam, "");
        return   outParam ;
    }*/
    public String getModuleMaxValueOld(String moduleName) {
//        return "";
        String jpql = "CALL sp_CreateMaxValue('" + moduleName + "',@maxvalue)";
        try {
            EntityManager entityManager = entityManagerFactory.createEntityManager();
            Query querySP = entityManager.createNativeQuery(jpql);
            // List<String> listValue = querySP.getResultList();
            querySP.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
//            querySP.executeUpdate() ;
            //  querySP.unwrap(SQLQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
            List rw = querySP.getResultList();
            jpql = "";
            /*if (listValue.size() > 0) {
                jpql = listValue.get(0);
            }*/

            Query queryNative = entityManager.createNativeQuery("SELECT maxMainKeyValue FROM ModuleMainKey  WHERE moduleName='" + moduleName + "'");
            queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
            List<String> rows = queryNative.getResultList();
            if (rows.size() > 0) {
                jpql = rows.get(0);
            }


            return jpql;
        } catch (Exception e) {
            log.info("获取最大值错误：" + e.getMessage());
            return "";
        }

    }


    public static List<String> convertToList(String content, String fgf) {
        return Arrays.stream(content.split(fgf)).map(f -> {
            return f.replaceAll("\\p{C}", "").trim();
        }).filter(f -> !f.equals("")).collect(Collectors.toList());

    }

    public static String getString(String content, String sourStr, String destStr) {
        int fromPos = content.indexOf(sourStr);
        if (fromPos == -1) {
            return null;
        }
        fromPos += sourStr.length();
        String newContent = content.substring(fromPos);
        int endPos = newContent.indexOf(destStr);
        if (endPos == -1) {
            return null;
        }
        return newContent.substring(0, endPos).trim();
    }

    /**
     * @param String time
     * @desc 字符串转时间戳
     * @example time="2019-04-19 00:00:00"
     **/

    public static Long getTimestamp(String time, String dateFormat) {
        Long timestamp = null;
        try {

            timestamp = new SimpleDateFormat(dateFormat, Locale.US).parse(time).getTime();
            ///1000*1000

        } catch (ParseException e) {
            e.printStackTrace();
        }
        return timestamp;
    }


    /**
     * @param Long timestamp
     * @desc 时间戳转字符串
     * @example timestamp=1558322327000
     **/
    public static String getStringTime(Long timestamp, String dateFormat) {
        if (timestamp == null) {
            return null;
        }
//        String date = new SimpleDateFormat("yyyy-MM-dd").format( new Date(timestamp));  // 获取只有年月日的时间
//        String datetime = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date(timestamp));  // 获取年月日时分秒
        String datetime = new SimpleDateFormat(dateFormat, Locale.US).format(new Date(timestamp));  // 获取年月日时分秒
        return datetime;
    }

    /**
     * 构造树形
     */

    public static Node findTreeNode(List<Node> lstNode, String nodeId) {
        for (Node node : lstNode) {
            if (node.getId().equals(nodeId)) {
//                root.add(node);
                return node;
            }
            if (node.getChildren() != null) {
                Node newNode = findTreeNode(node.getChildren(), nodeId);
                if (newNode != null) {
                    return newNode;
                }
            }
        }
        return null;

    }


    public static void addTreeNode(List<Node> lstNode, List<Node> root, Node node) {
        Node parentNode = findTreeNode(root, node.getParentId());
        if (parentNode != null) {
            if (Objects.isNull(parentNode.getChildren()) || findTreeNode(parentNode.getChildren(), node.getId()) == null)
                parentNode.addChild(node);
        } else {

            if (node.getParentId() == null || node.getParentId().equals("")) {
                if (findTreeNode(root, node.getId()) == null)
                    root.add(node);
            } else {
                Node parentNode1 = CollectionUtil.findOneByField(lstNode, "id", node.getParentId());
                Node newNode = Node.builder().id(parentNode1.getId())
                        .text(parentNode1.getText())
                        .parentId(parentNode1.getParentId()).build();

                newNode.addChild(node);
                addTreeNode(lstNode, root, newNode);
            }
        }

    }

    public static    void  setField(Object clazz, String fieldName, Object fieldValue) {
        try {

            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field==null)
                return ;
            field.setAccessible(true);
            if (field.isAccessible()) {
                if (field.getType() == Date.class)
                    field.set(clazz, DateUtil.parse((String) fieldValue, "yyyy-MM-dd"));
                else
                    field.set(clazz, fieldValue);
            }
        } catch (NoSuchFieldException | IllegalAccessException e) {
            throw new RuntimeException(e);
        }
    }

    public static String   getFieldValue( Object clazz, String fieldName) {
        try {

            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field==null)
                return null;
            field.setAccessible(true);
            if (field.isAccessible()) {
                if (field.getType() == String.class || field.getType()== Date.class || field.getType()== Date.class)
                    return  Objects.isNull(field.get(clazz))?"''": "'"+field.get(clazz).toString()+"'";
                else
                    return Objects.isNull(field.get(clazz))?"":field.get(clazz).toString();

//                return field.get(clazz).toString() ;
            }
            return null;
        } catch (NoSuchFieldException | IllegalAccessException e) {
//            throw new RuntimeException(e);
            log.error( String.format( "获取字段%s 值错误:"+e.getMessage(), fieldName ));
            return null;
        }
    }

    public static String   getFieldNormalValue( Object clazz, String fieldName) {
        try {

            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field==null)
                return null;
            field.setAccessible(true);
            if (field.isAccessible())
                return Objects.isNull(field.get(clazz))?null:field.get(clazz).toString();

            return null;
        } catch (NoSuchFieldException | IllegalAccessException e) {
//            throw new RuntimeException(e);
            log.error( String.format( "获取字段%s 值错误:"+e.getMessage(), fieldName ));
            return null;
        }
    }

    public static String phraseField(Object clazz,String fieldFlag,String expression)
    {
        if (!expression.contains(fieldFlag))
            return  expression;
        String fieldName = getString(expression, fieldFlag, fieldFlag) ;
        String content =getFieldValue(clazz,fieldName);

        expression = expression.replaceAll(fieldFlag+fieldName+fieldFlag,content);
        return  phraseField(clazz,fieldFlag,expression);
    }


    public  static <T>  List<T> getFilter(List<T> lstContent,String expression,String  fieldFlag) {
        return  lstContent.parallelStream().filter(f->{
            String newContent = phraseField(f, fieldFlag, expression) ;
//            Expression compiledExp = AviatorEvaluator.compile(newContent);
//            return (Boolean) compiledExp.execute();
            return (Boolean) MVEL.eval(newContent) ;

//             return (Boolean) AviatorEvaluator.execute(newContent);
        }).collect(Collectors.toList());
//        String newContent = phraseField(clazz, "", expression);


    }

    public static <T> String getQueryWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        String strWhere = query.getWhere();
        String keyWord = query.getKeyWord();
        if (Objects.isNull(strWhere) || Objects.isNull(keyWord))
            return "";
        boolean haveDelFlag = false;
        Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
        Class clazz = (Class) params[0];

        List<String> lstWhere = Arrays.asList(strWhere.split(","));
        String express = "";
        String template=" `%s`.contains('%s') ";
        String templateInt="`%s`==%s";
        for (String s : lstWhere) {

           Field field = Arrays.asList(clazz.getDeclaredFields())
                    .stream().filter(f -> f.getName().toLowerCase().equals(s.toLowerCase())).findFirst().orElse(null);

            if (Objects.nonNull(field)) {

                if (field.getType().equals(String.class)) {
                    if (StrUtil.isEmpty(express))
                        express = String.format(template, s, keyWord);
                    else
                         express = express.concat(" || ").concat(String.format(template, s, keyWord));
                }
                else
                    express = String.format(templateInt, s, keyWord);
            }

        }
        return  express;


    }


    /**
     * List 转 Page 对象
     *
     * @param list
     * @param pageable 分页参数
     * @param <T>
     * @return
     */
    public static <T> Page<T> convertList2PageVO(final List<T> list, final Pageable pageable) {
        if (CollectionUtils.isEmpty(list)) {
            return new PageImpl(new ArrayList<>(0), pageable, 0);
        }
        final List<T> ingredientVOS = list;
        final List<List<T>> partition = Lists.partition(list, pageable.getPageSize());
        List<T> pageContent = partition.get(pageable.getPageNumber());
        return new PageImpl<>(pageContent, pageable, ingredientVOS.size());
    }


    /**
     * @param list     全部数据
     * @param pageable 查询条件
     */
    public static <T> Page<T> startPage(List<T> list, Pageable pageable) {
        int total = list.size();
        if (CollectionUtil.isEmpty(list)) {
            return new PageImpl<>(new ArrayList<>(), pageable, total);
        }
        int pageNum = pageable.getPageNumber() + 1;
        int pageSize = pageable.getPageSize();
        int count = list.size();
        int pageCount;
        if (count % pageSize == 0) {
            pageCount = count / pageSize;
        } else {
            pageCount = count / pageSize + 1;
        }
        int fromIndex; // 开始索引
        int toIndex; // 结束索引
        if (pageNum != pageCount) {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = fromIndex + pageSize;
        } else {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = count;
        }
        List<T> pageList = new ArrayList<>();
        if (list.size() >= toIndex) {
            pageList = Optional.of(list.subList(fromIndex, toIndex)).orElse(new ArrayList<>());
        } else if (fromIndex < list.size()) {
            pageList = Optional.of(list.subList(fromIndex, list.size())).orElse(new ArrayList<>());
        }
        return new PageImpl<>(pageList, pageable, total);
    }

    /**
     * @param list     全部数据
     * @param total List总长度
     * @param pageable 查询条件
     */
    public static <T> Page<T> startPage(List<T> list, long total, Pageable pageable) {
        if (CollectionUtil.isEmpty(list)) {
            return new PageImpl<>(new ArrayList<>(), pageable, total);
        }
        int pageNum = pageable.getPageNumber() + 1;
        int pageSize = pageable.getPageSize();
        int count = list.size();
        int pageCount;
        if (count % pageSize == 0) {
            pageCount = count / pageSize;
        } else {
            pageCount = count / pageSize + 1;
        }
        int fromIndex; // 开始索引
        int toIndex; // 结束索引
        if (pageNum != pageCount) {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = fromIndex + pageSize;
        } else {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = count;
        }
        List<T> pageList = new ArrayList<>();
        if (list.size() >= toIndex) {
            pageList = Optional.of(list.subList(fromIndex, toIndex)).orElse(new ArrayList<>());
        } else if (fromIndex < list.size()) {
            pageList = Optional.of(list.subList(fromIndex, list.size())).orElse(new ArrayList<>());
        }
        return new PageImpl<>(pageList, pageable, total);
    }


    public static <T> void sortList(List<T> list, com.linkyoyo.reportaudit.query.Query<T> query) {
        if (query == null || query.getSort() == null || query.getSort().isEmpty()) {
            return;
        }

        list.sort(new Comparator<T>() {
            @Override
            public int compare(T o1, T o2) {

                Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
                Class clazz = (Class) params[0];

                Field field = Arrays.asList(clazz.getDeclaredFields())
                        .stream().filter(f -> f.getName().toLowerCase().equals(query.getSort().toLowerCase())).findFirst().orElse(null);
                Boolean sortAsc = Objects.isNull(query.getOrder())?true:query.getOrder().equalsIgnoreCase("asc")?true:false;
                if (Objects.nonNull(field)) {

                    field.setAccessible(true);
                    if (field.isAccessible()) {

                        try {
                           String data1= Objects.isNull(field.get(o1))?"":field.get(o1).toString();
                           String data2= Objects.isNull(field.get(o2))?"":field.get(o2).toString();
                           if (sortAsc)
                               return data1.compareTo(data2);
                           else
                               return data2.compareTo(data1);

                        } catch (IllegalAccessException e) {
                            throw new RuntimeException(e);
                        }


                    }


                }



                return 0;
            }
        });

    }


    public static  void CallOpenAiBySse(String baseString64,SseEmitter sseEmitter)
    {

        String azureKey = (aiConfig != null) ? aiConfig.getKey() : "REDACTED_AZURE_KEY";
        String azureEndpoint = (aiConfig != null) ? aiConfig.getUrl() : "https://bluecloud-bca-ai.openai.azure.com/";

        OpenAIClient client = new OpenAIClientBuilder()
                .credential(new AzureKeyCredential(azureKey))
                .endpoint(azureEndpoint)
                .serviceVersion(OpenAIServiceVersion.V2024_05_01_PREVIEW)
                .buildClient();


        List<ChatRequestMessage> chatMessages = new ArrayList<>();
        String baseString="";
        if (StrUtil.isNotEmpty(baseString64))
            baseString = String.format("data:image/jpeg;base64,%s", baseString64);


        chatMessages.add(new ChatRequestSystemMessage( "You are a helpful assistant. You will talk like a pirate."));

        if (!StrUtil.isEmptyIfStr(baseString))
            chatMessages.add(new ChatRequestUserMessage(Arrays.asList(
                    new ChatMessageTextContentItem("分析这张图片，用json格式输出，解析内容:标准编号，标题，发布日期，发布单位"),
                    new ChatMessageImageContentItem(
                            new ChatMessageImageUrl(baseString).setDetail(ChatMessageImageDetailLevel.AUTO))
            )));

        ChatCompletionsOptions chatCompletionsOptions = new ChatCompletionsOptions(chatMessages);
        chatCompletionsOptions.setMaxTokens(2048);
        chatCompletionsOptions.setTemperature(1.0);
        chatCompletionsOptions.setTopP(0.8);

        IterableStream<ChatCompletions> chatCompletionsStream = client.getChatCompletionsStream("gpt-4o-mini",
                chatCompletionsOptions);

        chatCompletionsStream
                .stream()

                .forEach(chatCompletions -> {
                    ChatResponseMessage delta = chatCompletions.getChoices().get(0).getDelta();
                    if (delta.getRole() != null) {
                    }
                    if (delta.getContent() != null) {

                        try {
                            // 发送 SSE 事件 （模拟延迟)
                            Thread.sleep(100);
                            sseEmitter.send(SseEmitter.event().name("answer").data( delta.getContent() ));
                        }
                        catch(Exception e)
                        { log.error("返回错误:{}",e.getMessage());}

                    }
                });


    }

    public static List callOpenAi(String baseString64){

        String azureKey = (aiConfig != null) ? aiConfig.getKey() : "REDACTED_AZURE_KEY";
        String azureEndpoint = (aiConfig != null) ? aiConfig.getUrl() : "https://bluecloud-bca-ai.openai.azure.com/";

        OpenAIClient client = new OpenAIClientBuilder()
                .credential(new AzureKeyCredential(azureKey))
                .endpoint(azureEndpoint)
                .serviceVersion(OpenAIServiceVersion.V2024_05_01_PREVIEW)
                .buildClient();


        List<ChatRequestMessage> chatMessages = new ArrayList<>();
        String baseString="";
        if (StrUtil.isNotEmpty(baseString64))
            baseString = String.format("data:image/jpeg;base64,%s", baseString64);
        /*try {

            InputStream imageInputStream = new FileInputStream("D:\\nginx-1.17.10\\html\\pdf\\0903.png");  //"http://127.0.0.1:8080/pdf/0903.png"
            byte[] imageBytes = new byte[imageInputStream.available()];
            imageInputStream.read(imageBytes);
            imageInputStream.close();

            baseString = String.format("data:image/jpeg;base64,%s", Base64.getEncoder().encodeToString(imageBytes));
        }
        catch (Exception e) {

        }*/

        chatMessages.add(new ChatRequestSystemMessage( "You are a helpful assistant. You will talk like a pirate."));
//        chatMessages.add(new ChatRequestUserMessage( "采用delphi写一个冒泡算法"));
        if (!StrUtil.isEmptyIfStr(baseString))
           chatMessages.add(new ChatRequestUserMessage(Arrays.asList(
                new ChatMessageTextContentItem("分析这张图片，用json格式输出，解析内容:标准编号，标题，发布日期，发布单位"),
                new ChatMessageImageContentItem(
                        new ChatMessageImageUrl(baseString).setDetail(ChatMessageImageDetailLevel.AUTO))
        )));

        ChatCompletionsOptions chatCompletionsOptions = new ChatCompletionsOptions(chatMessages);
        chatCompletionsOptions.setMaxTokens(2048);
        chatCompletionsOptions.setTemperature(1.0);
        chatCompletionsOptions.setTopP(0.8);
        ChatCompletions chatCompletions = client.getChatCompletions("gpt-4o-mini", chatCompletionsOptions);


        String returnMessage ="";
        for (ChatChoice choice : chatCompletions.getChoices()) {
            ChatResponseMessage message = choice.getMessage();
            returnMessage = returnMessage+message.getContent();
        }
//        ```json\n{\n  \"标准编号\": \"YC/T 384.2-2018\",\n  \"标题\": \"烟草企业安全生产标准化规范 第2部分:安全技术和现场规范\",\n  \"发布日期\": \"2018-04-03\",\n  \"发布单位\": \"国家烟草专卖局\"\n}\n```

        log.info("llm解析结果:{}",returnMessage);
        String jsonString = CommonFunc.getString(returnMessage,"```json\n{\n","\n}\n```");
        List<String> lst = new ArrayList<>() ;
        if  (StrUtil.isNotEmpty(jsonString)){
            JSONObject jsonObject = new JSONObject("{"+jsonString+"}");
            if (Objects.nonNull( jsonObject.get("标准编号") ))
              lst.add(jsonObject.get("标准编号").toString()) ;
            if (Objects.nonNull( jsonObject.get("标题") ))
                lst.add(jsonObject.get("标题").toString()) ;

            if (Objects.nonNull( jsonObject.get("发布日期") ))
                lst.add(jsonObject.get("发布日期").toString().concat(" 发布")) ;

            if (Objects.nonNull( jsonObject.get("发布单位") ))
                lst.add(jsonObject.get("发布单位").toString().concat(" 发布")) ;


            return lst;
        }

        return   null;

    }


    public static JSONObject callNewOpenAi(String baseString64){

        String azureKey = (aiConfig != null) ? aiConfig.getKey() : "REDACTED_AZURE_KEY";
        String azureEndpoint = (aiConfig != null) ? aiConfig.getUrl() : "https://bluecloud-bca-ai.openai.azure.com/";

        OpenAIClient client = new OpenAIClientBuilder()
                .credential(new AzureKeyCredential(azureKey))
                .endpoint(azureEndpoint)
                .serviceVersion(OpenAIServiceVersion.V2024_05_01_PREVIEW)
                .buildClient();


        List<ChatRequestMessage> chatMessages = new ArrayList<>();
        String baseString="";
        if (StrUtil.isNotEmpty(baseString64))
            baseString = String.format("data:image/jpeg;base64,%s", baseString64);
        /*try {

            InputStream imageInputStream = new FileInputStream("D:\\nginx-1.17.10\\html\\pdf\\0903.png");  //"http://127.0.0.1:8080/pdf/0903.png"
            byte[] imageBytes = new byte[imageInputStream.available()];
            imageInputStream.read(imageBytes);
            imageInputStream.close();

            baseString = String.format("data:image/jpeg;base64,%s", Base64.getEncoder().encodeToString(imageBytes));
        }
        catch (Exception e) {

        }*/

//        chatMessages.add(new ChatRequestSystemMessage( "分析这张图片，用json格式输出，解析内容:标准级别，标准编号，标题，发布日期，发布单位。其中标准级别的解析格式 ：GB,YC,YQ,Q/HNYC,Q/ZZYC,Q/KFYC,Q/LYYC,Q/AYYC,Q/HBYC,Q/XXYC,Q/JZYC,Q/PYYC,Q/XCYC,Q/LHYC,Q/SMXYC,Q/NYYC,Q/SQYC,Q/XYYC,Q/ZMDYC,Q/JYJC,Q/PDSYC,Q/ZKYC,DB5305,"));
//        chatMessages.add(new ChatRequestUserMessage( "采用delphi写一个冒泡算法"));
        chatMessages.add(new ChatRequestSystemMessage( "识别内容：标准级别，标准编号，标题，发布日期，发布单位，以json格式输出。其中标准级别：GB;YC;YQ;DB5305;Q/HNYC;Q/PDSYC;标准编号:需要包含标准级别完整解析。如何没有解析要求的内容，输出{}"));

        if (!StrUtil.isEmptyIfStr(baseString))
            chatMessages.add(new ChatRequestUserMessage(Arrays.asList(
                    new ChatMessageTextContentItem("分析"),
                    new ChatMessageImageContentItem(
                            new ChatMessageImageUrl(baseString).setDetail(ChatMessageImageDetailLevel.AUTO))
            )));

        ChatCompletionsOptions chatCompletionsOptions = new ChatCompletionsOptions(chatMessages);
        chatCompletionsOptions.setMaxTokens(2048);
        chatCompletionsOptions.setTemperature(1.0);
        chatCompletionsOptions.setTopP(0.8);
        ChatCompletions chatCompletions = client.getChatCompletions("us-east-gpt4o", chatCompletionsOptions);
        //gpt-4o-mini

        String returnMessage ="";
        for (ChatChoice choice : chatCompletions.getChoices()) {
            ChatResponseMessage message = choice.getMessage();
            returnMessage = returnMessage+message.getContent();
        }
//        ```json\n{\n  \"标准编号\": \"YC/T 384.2-2018\",\n  \"标题\": \"烟草企业安全生产标准化规范 第2部分:安全技术和现场规范\",\n  \"发布日期\": \"2018-04-03\",\n  \"发布单位\": \"国家烟草专卖局\"\n}\n```

        log.info("llm解析结果:{}",returnMessage);
        String jsonString = CommonFunc.getString(returnMessage,"{\n","\n}");
//                CommonFunc.getString(returnMessage,"```json\n{\n","\n}\n```");


        //        List<String> lst = new ArrayList<>() ;
        JSONObject obj=new JSONObject() ;
        if  (StrUtil.isNotEmpty(jsonString)){
            JSONObject jsonObject = new JSONObject("{"+jsonString+"}");
            //standardLevelName ,standardNo,publishDate,publishUnit,standardName
            if (Objects.nonNull( jsonObject.get("标准级别") ))
                obj.putOnce("standardLevelName",jsonObject.get("标准级别").toString()) ;

            if (Objects.nonNull( jsonObject.get("标准编号") ))
            {

               obj.putOnce("standardNo",jsonObject.get("标准编号").toString().contains(jsonObject.get("标准级别").toString())?jsonObject.get("标准编号").toString():
                       jsonObject.get("标准级别").toString().concat(" ").concat(jsonObject.get("标准编号").toString())) ;
            }

            if (Objects.nonNull( jsonObject.get("标准编号") ) && jsonObject.get("标准编号").toString().startsWith("Q/")
               && jsonObject.get("标准级别").toString().length()<=3)
            {
                obj.set("standardLevelName","Q/" +getString(jsonObject.get("标准编号").toString(),"Q/","YC")+"YC") ;

            }

            if (Objects.nonNull( jsonObject.get("标题") ))
                obj.putOnce("standardName",jsonObject.get("标题").toString()) ;


            if (Objects.nonNull( jsonObject.get("发布日期") ))
                obj.putOnce("publishDate",jsonObject.get("发布日期").toString().toLowerCase().replace("xx","01")) ;


            if (Objects.nonNull( jsonObject.get("发布单位") ))
             obj.putOnce("publishUnit",jsonObject.get("发布单位").toString()) ;


            return obj;
        }

        return   null;

    }

    public static  JSONObject callAi(File file)
    {

        JSONObject responseBody = null;
//        RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"),"");

        RequestBody requestBody = new MultipartBody.Builder().setType(MultipartBody.FORM)
                //上传的文件名称——参数不可省
                .addFormDataPart("file", file.getName(), RequestBody.create(MediaType.parse("image/png"), file))
                .build();

        // 从配置中获取URL和token
        String uploadUrl = "https://ai-verify.bluecloudatlas.cn/gateway/hcmsp-ai-keystone/api/files/upload";
        String authToken = "";

        if (linkyoyoAiConfig != null) {
            authToken = linkyoyoAiConfig.getToken();
        }

        Request request = new Request.Builder()
                .url(uploadUrl)
                .header("Authorization", "Bearer " + authToken)
                .post(requestBody)
                .build();
        Response response = null;
        try {
            OkHttpClient okHttpClient = (httpClientFactory != null)
                    ? httpClientFactory.createClientSeconds(60, 60, 60)
                    : new OkHttpClient();
            response = okHttpClient.newCall(request).execute();
            int status = response.code();
            if (response.isSuccessful()) {
               JSONObject   rtnJson = new JSONObject(response.body().string()) ;
               String fileId= rtnJson.get("id").toString() ;

                // 使用共享的请求体构建器
                JSONObject chatRequest = LinkyoyoRequestBuilder.buildFileChatRequest(fileId);
                requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"),
                        chatRequest.toString());

                 // 从配置中获取URL和token
                 String chatUrl = "https://ai-verify.bluecloudatlas.cn/gateway/hcmsp-ai-keystone/api/chat-messages";

                 if (linkyoyoAiConfig != null) {
                     chatUrl = linkyoyoAiConfig.getUrl();
                 }

                 request = new Request.Builder()
                        .url(chatUrl)
                        .header("Authorization", "Bearer " + authToken)
                        .post(requestBody)
                        .build();

                response = okHttpClient.newCall(request).execute();
                if (response.isSuccessful()) {
                     rtnJson = new JSONObject(response.body().string());
                     String content = rtnJson.getJSONObject("data").get("answer").toString() ;

                    String jsonString = CommonFunc.getString(content,"```json\n{\n","\n}\n```");
                    log.info("ai 解析内容：{}",jsonString);
//        List<String> lst = new ArrayList<>() ;
                    JSONObject obj=new JSONObject() ;
                    if  (StrUtil.isNotEmpty(jsonString)) {
                        JSONObject jsonObject = new JSONObject("{" + jsonString + "}");
                        //standardLevelName ,standardNo,publishDate,publishUnit,standardName
                        if (Objects.nonNull( jsonObject.get("标准级别") ))
                            obj.putOnce("standardLevelName",jsonObject.get("标准级别").toString()) ;

                        if (Objects.nonNull( jsonObject.get("标准号") ))
                        {

                            obj.putOnce("standardNo",jsonObject.get("标准号").toString().contains(jsonObject.get("标准级别").toString())?jsonObject.get("标准号").toString():
                                    jsonObject.get("标准级别").toString().concat(" ").concat(jsonObject.get("标准号").toString())) ;
                        }

                        if (Objects.nonNull( jsonObject.get("标准号") ) && jsonObject.get("标准号").toString().startsWith("Q/")
                                && jsonObject.get("标准级别").toString().length()<=3)
                        {
                            obj.set("standardLevelName","Q/" +getString(jsonObject.get("标准号").toString(),"Q/","YC")+"YC") ;

                        }

                        if (Objects.nonNull( jsonObject.get("标准名称") ))
                            obj.putOnce("standardName",jsonObject.get("标准名称").toString()) ;


                        if (Objects.nonNull( jsonObject.get("标准发布日期") ))
                            obj.putOnce("publishDate",jsonObject.get("标准发布日期").toString().toLowerCase().replace("xx","01")) ;


                        if (Objects.nonNull( jsonObject.get("标准发布单位") ))
                            obj.putOnce("publishUnit",jsonObject.get("标准发布单位").toString()) ;


                        return obj;

                    }
                }




             //   return JSONObject.(response.body().string());
            }
        } catch (Exception e) {
            log.error("okhttp3 post error >> ex = {}", e.getMessage());
        } finally {
            if (response != null) {
//                response.();
            }
        }

        return null;
    }


    public static File createTempFile(byte[] bytes, String fileName, String fileExtension) throws IOException {
        // 创建ByteArrayInputStream来读取byte数组
        ByteArrayInputStream bis = new ByteArrayInputStream(bytes);

        // 创建ByteArrayOutputStream来暂存写入的数据
        ByteArrayOutputStream bos = new ByteArrayOutputStream();

        // 将ByteArrayInputStream的内容写入ByteArrayOutputStream
        byte[] buffer = new byte[1024];
        int read;
        while ((read = bis.read(buffer)) != -1) {
            bos.write(buffer, 0, read);
        }

        // 将ByteArrayOutputStream的内容写入到实际的文件中
        File tempFile = File.createTempFile(fileName, fileExtension);
        try (FileOutputStream fos = new FileOutputStream(tempFile)) {
            fos.write(bos.toByteArray());
        }

        return tempFile;
    }

    /**
     * 调用AI服务解析内容
     * 支持Azure OpenAI和DeepSeek两种模型
     *
     * @param content 需要解析的内容
     * @return 解析结果的JSON对象
     */
    public static JSONObject callAiWithOkHttp(String content) {

        if (aiConfig == null) {
            log.error("AiConfig未注入，使用默认配置");
            return callAiWithOkHttp(content, true, "https://subs1-5.openai.azure.com/",
                "REDACTED_AZURE_OPENAI_KEY_2",
                "gpt-4o-5", "2024-05-01-preview",
                "解析内容：标准类型（国标   ||   行业标准 ||  企业标准/地方标准）,标准号,标准中文名,标准英文名，发布日期,实施日期,标准状态,发布单位,提出单位,起草单位,起草人,范围,规范性引用文件,**前言,引言,术语和定义,参考文献**;以json格式输出");
        }
        return callAiWithOkHttp(content, aiConfig.isAzure(), aiConfig.getUrl(), aiConfig.getKey(),
                              aiConfig.getModel(), aiConfig.getVersion(), aiConfig.getPrompt());
    }

    /**
     * 调用DeepSeek AI服务解析内容
     *
     * @param content 需要解析的内容
     * @return 解析结果的JSON对象
     */
    public static JSONObject callDeepSeekAi(String content) {


        if (aiConfig == null) {
            log.error("AiConfig未注入，使用默认配置");
            return callAiWithOkHttp(content, false, "https://api.deepseek.com/v1/chat/completions",
                "REDACTED_DEEPSEEK_API_KEY", "deepseek-chat", "",
                "解析内容：标准类型（国标   ||   行业标准 ||  企业标准/地方标准）,标准号,标准中文名,标准英文名，发布日期,实施日期,标准状态,发布单位,提出单位,起草单位,起草人,范围,规范性引用文件,**前言,引言,术语和定义,参考文献**;以json格式输出");
        }
        return callAiWithOkHttp(content, aiConfig.isDeepseekIsAzure(), aiConfig.getDeepseekUrl(),
                              aiConfig.getDeepseekKey(), aiConfig.getDeepseekModel(), "", aiConfig.getDeepseekPrompt());
    }

    /**
     * 调用AI服务解析内容 - 使用配置参数
     * 支持Azure OpenAI和DeepSeek两种模型
     *
     * @param content 需要解析的内容
     * @param isAzure 是否使用Azure OpenAI
     * @param url API端点URL
     * @param key API密钥
     * @param model 模型名称
     * @param version API版本（仅Azure需要）
     * @param promptMarkDown 提示词
     * @return 解析结果的JSON对象
     */

    /**
     * 创建一个配置了SSL和超时的OkHttpClient
     * 委托给HttpClientFactory，如果factory不可用则使用内置实现
     *
     * @return 配置好的OkHttpClient实例
     * @throws Exception 如果创建过程中发生错误
     */
    private static OkHttpClient createSecureHttpClient() throws Exception {
        if (httpClientFactory != null) {
            return httpClientFactory.createClientSeconds(60, 120, 60);
        }
        // Fallback: factory未注入时的内置实现
        final TrustManager[] trustAllCerts = new TrustManager[] {
            new X509TrustManager() {
                @Override
                public void checkClientTrusted(java.security.cert.X509Certificate[] chain, String authType) {
                }

                @Override
                public void checkServerTrusted(java.security.cert.X509Certificate[] chain, String authType) {
                }

                @Override
                public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                    return new java.security.cert.X509Certificate[]{};
                }
            }
        };

        final SSLContext sslContext = SSLContext.getInstance("SSL");
        sslContext.init(null, trustAllCerts, new java.security.SecureRandom());

        return new OkHttpClient.Builder()
            .sslSocketFactory(sslContext.getSocketFactory(), (X509TrustManager) trustAllCerts[0])
            .hostnameVerifier((hostname, session) -> true)
            .connectTimeout(60, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build();
    }

    /**
     * 构建AI请求的JSON请求体
     *
     * @param promptMarkDown 提示词
     * @param content 内容
     * @param model 模型名称（仅DeepSeek需要）
     * @param isAzure 是否Azure OpenAI
     * @return 构建好的JSON请求体
     */
    private static JSONObject buildRequestJson(String promptMarkDown, String content, String model, boolean isAzure) {
        JSONObject jsonRequest = new JSONObject();
        jsonRequest.set("temperature", 0.1);
        jsonRequest.set("max_tokens", 8000);

        if (!isAzure) {
            jsonRequest.set("model", model);
        }

        // 构建消息数组
        JSONObject systemMessage = new JSONObject();
        systemMessage.set("role", "system");
        systemMessage.set("content", "You are a helpful assistant.");

        JSONObject userMessage = new JSONObject();
        userMessage.set("role", "user");
        userMessage.set("content", promptMarkDown + "\n" + content);

        jsonRequest.set("messages", new JSONObject[]{systemMessage, userMessage});

        return jsonRequest;
    }

    /**
     * 从AI响应中提取并解析内容
     *
     * @param jsonResponse AI响应的JSON对象
     * @return 解析后的JSON对象
     */
    private static JSONObject extractAndParseContent(JSONObject jsonResponse) {
        // 从响应中提取内容文本
        String content_text = jsonResponse.getJSONArray("choices")
            .getJSONObject(0)
            .getJSONObject("message")
            .getStr("content");

        // 尝试解析内容为JSON
        try {
            String jsonString = substringBetween(content_text,"\n{","}\n");
            log.info("AI解析内容：{}", jsonString);

            if (StrUtil.isEmpty(jsonString)) {
                return null;
            }

            return JSONUtil.parseObj("{" + jsonString + "}");
        } catch (Exception e) {
            log.error("解析AI响应内容为JSON失败: {}", e.getMessage());
            // 如果解析失败，返回原始内容包装在JSON中
            JSONObject result = new JSONObject();
            result.set("content", content_text);
            return result;
        }
    }

    /**
     * 调用AI服务解析内容 - 使用配置参数
     * 支持Azure OpenAI和DeepSeek两种模型
     *
     * @param content 需要解析的内容
     * @param isAzure 是否使用Azure OpenAI
     * @param url API端点URL
     * @param key API密钥
     * @param model 模型名称
     * @param version API版本（仅Azure需要）
     * @param promptMarkDown 提示词
     * @return 解析结果的JSON对象
     */
    public static JSONObject callAiWithOkHttp(String content, boolean isAzure, String url, String key,
                                             String model, String version, String promptMarkDown) {
        try {
            // 创建安全的HTTP客户端
            OkHttpClient client = createSecureHttpClient();
            log.info("创建OkHttpClient并设置超时: 连接超时=60秒, 读取超时=120秒, 写入超时=60秒");

            // 准备请求URL
            String endpoint;
            if (isAzure) {
                if (!url.endsWith("/")) {
                    url = url + "/";
                }
                endpoint = url + "openai/deployments/" + model + "/chat/completions?api-version=" + version;
                log.info("请求Azure OpenAI端点: {}", endpoint);
            } else {
                endpoint = url;
                log.info("请求DeepSeek端点: {}", endpoint);
                log.info("使用模型: {}", model);
            }

            // 构建请求体
            JSONObject jsonRequest = buildRequestJson(promptMarkDown, content, model, isAzure);
            String jsonBody = jsonRequest.toString();
            RequestBody requestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);

            // 构建请求
            Request.Builder requestBuilder = new Request.Builder()
                .url(endpoint)
                .addHeader("Content-Type", "application/json")
                .post(requestBody);

            // 根据API类型添加不同的认证头
            if (isAzure) {
                requestBuilder.addHeader("api-key", key);
            } else {
                requestBuilder.addHeader("Authorization", "Bearer " + key);
                log.info("请求头信息: Authorization=Bearer {}, Content-Type={}", key, "application/json");
            }

            Request request = requestBuilder.build();

            // 执行请求
            Response response = client.newCall(request).execute();

            if (response.isSuccessful()) {
                String responseBody = response.body().string();
                log.info("AI响应: {}", responseBody);

                // 解析响应
                JSONObject jsonResponse = JSONUtil.parseObj(responseBody);

                // 提取和解析内容（Azure和DeepSeek的响应格式相同）
                return extractAndParseContent(jsonResponse);
            } else {
                String errorBody = "";
                try {
                    errorBody = response.body().string();
                    log.error("AI请求失败详情: {}", errorBody);
                } catch (Exception e) {
                    log.error("无法读取错误响应体: {}", e.getMessage());
                }

                log.error("AI请求失败: {} - {}", response.code(), response.message());
                log.error("请求URL: {}", request.url());
                log.error("请求头: {}", request.headers());

                JSONObject errorResult = new JSONObject();
                errorResult.set("error", "请求失败: " + response.code() + " - " + response.message());
                errorResult.set("errorDetails", errorBody);
                return errorResult;
            }

        } catch (Exception e) {
            log.error("调用AI服务异常: {}", e.getMessage(), e);
            JSONObject errorResult = new JSONObject();
            errorResult.set("error", "调用AI服务异常: " + e.getMessage());
            return errorResult;
        }
    }

    /**
     * 从字符串中截取指定开始和结束字符串之间的内容，支持嵌套的结束字符
     *
     * @param source 源字符串
     * @param start 开始字符串
     * @param end 结束字符串
     * @return 截取的内容，如果未找到则返回空字符串
     */
    public static String substringBetween(String source, String start, String end) {
        if (source == null || start == null || end == null) {
            return "";
        }

        int startIndex = source.indexOf(start);
        if (startIndex == -1) {
            return "";
        }

        startIndex += start.length();
        // 找到最后一个结束字符
        int endIndex = source.lastIndexOf(end);
        if (endIndex == -1 || endIndex <= startIndex) {
            return "";
        }

        return source.substring(startIndex, endIndex);
    }

    public static JSONObject callAi(String query) {



        OkHttpClient okHttpClient = (httpClientFactory != null)
                ? httpClientFactory.createClientSeconds(60, 60, 60)
                : new OkHttpClient().newBuilder()
                .connectTimeout(1, TimeUnit.MINUTES)
                .readTimeout(1, TimeUnit.MINUTES)
                .writeTimeout(1, TimeUnit.MINUTES)
                .build();
        String orgQuery = query;
        try {

            // 使用共享的请求体构建器
            JSONObject requestJson = LinkyoyoRequestBuilder.buildRequest(query, "gpt-4o-5", 0f, 4096);

            String requestContent = requestJson.toString();
            RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"), requestContent);

            Request request = new Request.Builder()
                    .url(linkyoyoAiConfig.getUrl())
                    .header("Authorization", "Bearer " + linkyoyoAiConfig.getToken())
                    .post(requestBody)
                    .build();
            Response response = null;
            try {

                response = okHttpClient.newCall(request).execute();
            } catch (Exception e) {
                log.error("blue ai 解析 error:{},query:{}", e.getMessage(),orgQuery);
                return null;
            }
            if (response.isSuccessful()) {
                JSONObject rtnJson = new JSONObject(response.body().string());
                String content = rtnJson.getJSONObject("data").get("answer").toString();

                String jsonString = substringBetween(content,"\n{","}\n");
                log.info("AI解析内容：{}", jsonString);

                if (StrUtil.isEmpty(jsonString)) {
                    return null;
                }

                return JSONUtil.parseObj("{" + jsonString + "}");
            }




        } catch (Exception e) {
            log.error("okhttp3 post error >> ex = {}", e.getMessage());
        } finally {

        }

        return null;
    }

}


