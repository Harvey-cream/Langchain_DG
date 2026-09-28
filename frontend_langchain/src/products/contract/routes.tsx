import React from 'react';
import { Route, Routes } from 'react-router-dom';
import ContractListPage from './ContractListPage';
import ContractVersionPage from './ContractVersionPage';

const ContractRoutes: React.FC = () => (
  <Routes>
    <Route index element={<ContractListPage />} />
    <Route path=":contractId" element={<ContractVersionPage />} />
  </Routes>
);

export default ContractRoutes;
