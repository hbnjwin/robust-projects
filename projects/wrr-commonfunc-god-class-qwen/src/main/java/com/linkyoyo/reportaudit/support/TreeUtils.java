package com.linkyoyo.reportaudit.support;

import cn.hutool.core.collection.CollectionUtil;

import java.util.List;
import java.util.Objects;

/**
 * 树结构工具类
 * 从 CommonFunc 中提取的树节点查找和添加操作
 */
public class TreeUtils {

    /**
     * 在树中递归查找指定 ID 的节点
     *
     * @param lstNode 节点列表
     * @param nodeId  要查找的节点 ID
     * @return 找到的节点，未找到返回 null
     */
    public static Node findTreeNode(List<Node> lstNode, String nodeId) {
        for (Node node : lstNode) {
            if (node.getId().equals(nodeId)) {
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

    /**
     * 将节点添加到树中正确的位置
     * 如果父节点不存在则创建中间节点
     *
     * @param lstNode 所有节点列表
     * @param root    根节点列表
     * @param node    要添加的节点
     */
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
}
