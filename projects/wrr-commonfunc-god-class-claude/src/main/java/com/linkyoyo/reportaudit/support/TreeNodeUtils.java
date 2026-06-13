package com.linkyoyo.reportaudit.support;

import cn.hutool.core.collection.CollectionUtil;

import java.util.List;
import java.util.Objects;

public class TreeNodeUtils {

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
