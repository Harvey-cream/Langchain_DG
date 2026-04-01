import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Card, Form, Input, Typography, Alert, Spin } from 'antd';
import { login } from '../../services/api';
import { LoginRequest, FormErrors } from './types';
import { SM2Utils } from '../../utils/sm2';

const { Title, Text } = Typography;

type LoginViewProps = {
  formData: LoginRequest;
  errors: FormErrors;
  loading: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (e: React.FormEvent) => void;
};

const LoginView: React.FC<LoginViewProps> = ({ formData, errors, loading, onChange, onSubmit }) => {
  return (
    <Card className="auth-card" variant="outlined">
      <Title level={2} className="auth-title">用户登录</Title>

      {errors.submit && (
        <Alert
          type="error"
          showIcon
          message={errors.submit}
          style={{ marginBottom: 16 }}
        />
      )}

      <Form layout="vertical" onSubmitCapture={onSubmit}>
        <Form.Item
          label="邮箱"
          validateStatus={errors.email ? 'error' : ''}
          help={errors.email}
        >
          <Input size="large" type="email" id="email" name="email" value={formData.email}
            onChange={onChange}
            placeholder="请输入邮箱"
          />
        </Form.Item>

        <Form.Item
          label="密码"
          validateStatus={errors.password ? 'error' : ''}
          help={errors.password}
        >
          <Input.Password size="large" id="password" name="password" value={formData.password}
            onChange={onChange}
            placeholder="请输入密码"
          />
        </Form.Item>

        <Button type="primary" htmlType="submit" className="auth-submit" size="large" block disabled={loading}>
          {loading ? <Spin size="small" /> : '登录'}
        </Button>
      </Form>

      <Text className="auth-link-text">
        没有账号？ <Link to="/register">去注册</Link>
      </Text>
    </Card>
  );
};

const Login: React.FC = () => {
  const navigate = useNavigate();

  // 表单状态
  const [formData, setFormData] = useState<LoginRequest>({
    email: '',
    password: '',
  });

  // 错误信息
  const [errors, setErrors] = useState<FormErrors>({});

  // 加载状态
  const [loading, setLoading] = useState(false);

  // 处理表单输入变化
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));

    // 清除对应字段的错误信息
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  // 表单验证
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    if (!formData.email.trim()) {
      newErrors.email = '邮箱不能为空';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = '请输入有效的邮箱地址';
    }

    if (!formData.password) {
      newErrors.password = '密码不能为空';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 处理表单提交
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // 验证表单
    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      console.log('开始登录，原始表单数据:', formData);
      // 加密密码
      const encryptedPassword = SM2Utils.encrypt(formData.password);
      console.log('加密后的密码:', encryptedPassword);
      
      const encryptedFormData = {
        ...formData,
        password: encryptedPassword
      };
      console.log('加密后的表单数据:', encryptedFormData);
      
      console.log('准备发送登录请求...');
      const response = await login(encryptedFormData);
      console.log('登录请求响应:', response);

      if (response.success) {
          // 登录成功，存储token（如果有）
          if (response.data?.token) {
            localStorage.setItem('token', response.data.token);
          }
          // 跳转到聊天页面
          navigate('/chat');
        } else {
          const errorMessage = response?.msg || response?.message || '登录失败，请稍后重试';
          setErrors({ submit: errorMessage });
        }
    } catch (error) {
      console.error('登录失败，错误信息:', error);
      setErrors({ submit: '登录失败，请稍后重试' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <LoginView
        formData={formData}
        errors={errors}
        loading={loading}
        onChange={handleChange}
        onSubmit={handleSubmit}
      />
    </div>
  );
};

export default Login;
