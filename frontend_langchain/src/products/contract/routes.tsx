import React from 'react';
import { Route, Routes } from 'react-router-dom';
import ContractListPage from './ContractListPage';
import ContractVersionPage from './ContractVersionPage';
import ContractPolicyPage from './ContractPolicyPage';
import ContractKnowledgePage from './ContractKnowledgePage';

const ContractRoutes: React.FC = () => (
  <Routes>
    <Route index element={<ContractListPage />} />
    <Route path="policies" element={<ContractPolicyPage />} />
    <Route path="knowledge" element={<ContractKnowledgePage />} />
    <Route path=":contractId" element={<ContractVersionPage />} />
  </Routes>
);

export default ContractRoutes;
