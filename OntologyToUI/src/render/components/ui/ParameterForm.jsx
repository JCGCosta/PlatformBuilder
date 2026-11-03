import { useState } from 'react';
import { Form, InputNumber, Button } from 'antd';
import { findBmParams } from '../../../lib/utils.js';

/**
 * Generic parameter form that reads params from a BusinessModel, renders
 * input fields, submits to the API, and delegates result handling to the parent.
 *
 * Props:
 *   bm              – BusinessModel URI
 *   parameters      – parameters index (keyed by BM local name)
 *   onSuccess       – called with parsed JSON when response is ok
 *   onError         – called with error message string on failure
 *   fieldComponent  – optional fn(type, label) => ReactNode to override field rendering
 *   resetOnSuccess  – if true, resets form fields after a successful submit (default: false)
 *   onLoadingChange – optional fn(boolean) called when loading state changes
 */
export default function ParameterForm({
  bm,
  endpointPath,
  apiBaseUrl,
  parameters,
  onSuccess,
  onError,
  fieldComponent,
  resetOnSuccess = false,
  onLoadingChange,
}) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const bmLocalName = bm?.split('#')[1] || bm?.split('/').pop() || '';
  const bmParams = findBmParams(parameters, bmLocalName);

  const setLoadingState = (val) => {
    setLoading(val);
    onLoadingChange?.(val);
  };

  const handleSubmit = async (values) => {
    if (!endpointPath) {
      onError?.('Could not determine API endpoint from BusinessModel');
      return;
    }

    setLoadingState(true);
    try {
      // Build a map of param label → type for file detection
      const paramTypeMap = {};
      bmParams.forEach(p => {
        paramTypeMap[p.label] = p.type?.toLowerCase() || 'str';
      });

      const queryParams = new URLSearchParams();
      const formData = new FormData();
      let hasFiles = false;

      Object.entries(values).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') return;

        const paramType = paramTypeMap[key];
        const isFileType = paramType === 'uploadfile' || paramType === 'file';

        if (isFileType) {
          hasFiles = true;
          if (Array.isArray(value) && value[0]?.originFileObj) {
            formData.append(key, value[0].originFileObj);
          } else if (value?.fileList?.[0]?.originFileObj) {
            formData.append(key, value.fileList[0].originFileObj);
          } else if (value instanceof File) {
            formData.append(key, value);
          }
        } else {
          // DatePicker values have a _d moment property
          if (value?._d) {
            queryParams.append(key, value.format('YYYY-MM-DD'));
          } else {
            queryParams.append(key, value);
          }
        }
      });

      const baseUrl = apiBaseUrl || 'http://127.0.0.1:5000';
      let url = `${baseUrl}${endpointPath}`;
      const qs = queryParams.toString();
      if (qs) url = `${url}?${qs}`;

      const response = await fetch(url, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        ...(hasFiles ? { body: formData } : {}),
      });

      const data = await response.json();

      if (response.ok) {
        if (resetOnSuccess) form.resetFields();
        onSuccess?.(data);
      } else {
        onError?.(data.detail || data.desc || 'An error occurred.');
      }
    } catch {
      onError?.('Could not connect to the API. Is the server running?');
    } finally {
      setLoadingState(false);
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      disabled={loading}
      style={{ marginBottom: 16 }}
    >
      {bmParams.map((param, index) => {
        const paramType = param.type?.toLowerCase();
        const isFileField = paramType === 'uploadfile' || paramType === 'file';
        return (
          <Form.Item
            key={index}
            name={param.label}
            label={param.label}
            rules={[{ required: true, message: `${isFileField ? 'Select' : 'Enter'} ${param.label}` }]}
            valuePropName={isFileField ? 'fileList' : 'value'}
            getValueFromEvent={isFileField ? (e) => (Array.isArray(e) ? e : e?.fileList) : undefined}
          >
            {fieldComponent
              ? fieldComponent(param.type, param.label)
              : <InputNumber style={{ width: '100%' }} placeholder={param.label} />
            }
          </Form.Item>
        );
      })}
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          {loading ? 'Submitting...' : 'Submit'}
        </Button>
      </Form.Item>
    </Form>
  );
}
