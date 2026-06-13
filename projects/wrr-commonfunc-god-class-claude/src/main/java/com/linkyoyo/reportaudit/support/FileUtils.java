package com.linkyoyo.reportaudit.support;

import java.io.*;

public class FileUtils {

    public static void deleteFolder(File folder) throws Exception {
        if (!folder.exists()) {
            throw new Exception("文件不存在");
        }
        File[] files = folder.listFiles();
        if (files != null) {
            for (File file : files) {
                if (file.isDirectory()) {
                    deleteFolder(file);
                } else {
                    file.delete();
                }
            }
        }
        folder.delete();
    }

    public static File createTempFile(byte[] bytes, String fileName, String fileExtension) throws IOException {
        ByteArrayInputStream bis = new ByteArrayInputStream(bytes);
        ByteArrayOutputStream bos = new ByteArrayOutputStream();

        byte[] buffer = new byte[1024];
        int read;
        while ((read = bis.read(buffer)) != -1) {
            bos.write(buffer, 0, read);
        }

        File tempFile = File.createTempFile(fileName, fileExtension);
        try (FileOutputStream fos = new FileOutputStream(tempFile)) {
            fos.write(bos.toByteArray());
        }

        return tempFile;
    }
}
