package com.linkyoyo.reportaudit.support;

import java.io.*;

/**
 * 文件操作工具类
 * 从 CommonFunc 中提取的文件读写操作
 */
public class FileHelper {

    /**
     * 递归删除目录及其所有内容
     *
     * @param folder 要删除的目录
     * @throws Exception 如果目录不存在
     */
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
     * 从字节数组创建临时文件
     *
     * @param bytes         文件内容
     * @param fileName      临时文件名前缀
     * @param fileExtension 临时文件扩展名
     * @return 创建的临时文件
     * @throws IOException 如果创建过程中发生错误
     */
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
}
