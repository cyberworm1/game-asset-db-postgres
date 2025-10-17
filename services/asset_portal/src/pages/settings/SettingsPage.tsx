import {
  Button,
  Card,
  CardBody,
  CardHeader,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Select,
  Stack,
  Switch,
  Textarea
} from '@chakra-ui/react';

const SettingsPage = () => (
  <Stack spacing={6} maxW="3xl">
    <Card>
      <CardHeader>
        <Heading size="md">Notifications</Heading>
      </CardHeader>
      <CardBody>
        <Stack spacing={4}>
          <FormControl display="flex" alignItems="center">
            <FormLabel htmlFor="digest" flex="1">
              Daily summary digest
            </FormLabel>
            <Switch id="digest" defaultChecked />
          </FormControl>
          <FormControl display="flex" alignItems="center">
            <FormLabel htmlFor="websocket" flex="1">
              Real-time notifications
            </FormLabel>
            <Switch id="websocket" defaultChecked />
          </FormControl>
          <FormControl>
            <FormLabel>Email preferences</FormLabel>
            <Select defaultValue="important">
              <option value="all">All events</option>
              <option value="important">Only important</option>
              <option value="none">Mute</option>
            </Select>
          </FormControl>
        </Stack>
      </CardBody>
    </Card>
    <Card>
      <CardHeader>
        <Heading size="md">API tokens</Heading>
      </CardHeader>
      <CardBody>
        <Stack spacing={4}>
          <FormControl>
            <FormLabel>Generate new token</FormLabel>
            <Input placeholder="Label (e.g. Houdini plugin)" />
          </FormControl>
          <Button colorScheme="purple">Create token</Button>
        </Stack>
      </CardBody>
    </Card>
    <Card>
      <CardHeader>
        <Heading size="md">Integrations</Heading>
      </CardHeader>
      <CardBody>
        <Stack spacing={4}>
          <FormControl>
            <FormLabel>Webhook URL</FormLabel>
            <Input placeholder="https://hooks.studio.internal/asset-events" />
          </FormControl>
          <FormControl>
            <FormLabel>Automation notes</FormLabel>
            <Textarea placeholder="Document automation expectations for pipelines" rows={4} />
          </FormControl>
          <Button colorScheme="purple">Save changes</Button>
        </Stack>
      </CardBody>
    </Card>
  </Stack>
);

export default SettingsPage;
