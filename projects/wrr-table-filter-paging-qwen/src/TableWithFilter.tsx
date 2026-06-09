import React, { useState } from "react";
import { Table, Select, Button } from "antd";
import { useRequest } from "ahooks";

interface UserRecord {
  id: number;
  name: string;
  status: string;
  email: string;
}

const TableWithFilter: React.FC = () => {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });

  const { data, loading } = useRequest(
    () => fetch(`/api/users?status=${filters.status}&page=${pagination.current}&pageSize=${pagination.pageSize}`),
    { refreshDeps: [filters, pagination] }
  );

  const handleFilterChange = (value: string) => {
    setFilters({ ...filters, status: value });
    // BUG: pagination not reset when filter changes
  };

  return (
    <div>
      <Select onChange={handleFilterChange} placeholder="Filter by status" />
      <Table
        dataSource={data?.list}
        loading={loading}
        pagination={{ ...pagination, onChange: (p) => setPagination({ ...pagination, current: p }) }}
      />
    </div>
  );
};

export default TableWithFilter;
