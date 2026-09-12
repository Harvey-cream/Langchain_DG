import React from 'react';
import { Route, Routes } from 'react-router-dom';
import ContractListPage from '../../pages/contract/ContractListPage';
import ContractVersionPage from '../../pages/contract/ContractVersionPage';

const ContractRoutes: React.FC = () => (
  <Routes>
    <Route index element={<ContractListPage />} />
    <Route path=":contractId" element={<ContractVersionPage />} />
  </Routes>
);

export default ContractRoutes;
